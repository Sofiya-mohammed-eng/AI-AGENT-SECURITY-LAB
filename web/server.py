"""Local web chat for the agent. Start with:  python3 main.py web

Security notes: binds to 127.0.0.1 only; the API key stays on the server;
Host and Origin are checked (blocks DNS-rebinding and cross-site posts);
JSON content type, body size, session count and request rate are limited;
a strict Content-Security-Policy is sent; sessions are server-issued.
"""
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent.agent import Conversation
from agent.guards import RateLimiter
from agent.logger import AgentLogger, get_default_logger

STATIC = Path(__file__).parent / "static"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
MAX_BODY, MAX_SESSIONS, IDLE_SECONDS = 8192, 100, 1800
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class Recorder(AgentLogger):
    """Writes the normal audit log and also keeps this request's events."""

    def __init__(self, base):
        super().__init__(path=base.path, enabled=base.enabled)
        self.events = []

    def log(self, event, **fields):
        self.events.append((event, fields))
        super().log(event, **fields)


class Session:
    def __init__(self, client, base_logger):
        self.recorder = Recorder(base_logger)
        self.convo = Conversation(client, logger=self.recorder)
        self.limiter, self.lock, self.last = RateLimiter(20, 60), threading.Lock(), time.monotonic()


class ChatApp:
    def __init__(self, client, logger=None):
        self.client, self.logger = client, logger or get_default_logger()
        self.sessions, self.lock = {}, threading.Lock()
        self.global_limiter = RateLimiter(60, 60)

    def _session(self, sid):
        with self.lock:
            now = time.monotonic()
            for k in [k for k, s in self.sessions.items() if now - s.last > IDLE_SECONDS]:
                del self.sessions[k]
            if sid in self.sessions:
                return sid, self.sessions[sid]
            if len(self.sessions) >= MAX_SESSIONS:
                return None, None
            sid = secrets.token_urlsafe(16)
            self.sessions[sid] = Session(self.client, self.logger)
            return sid, self.sessions[sid]

    def chat(self, sid, message):
        sid, s = self._session(sid)
        if s is None:
            return 503, {"error": "Server is busy. Try again later."}
        if not (self.global_limiter.allow() and s.limiter.allow()):
            return 429, {"error": "Too many messages. Wait a moment."}
        with s.lock:
            s.last = time.monotonic()
            s.recorder.events.clear()
            answer = s.convo.ask(message)
            tools = [{"name": f["tool"], "flagged": f["flagged_as_injection"]}
                     for e, f in s.recorder.events if e == "tool_call"]
        return 200, {"session_id": sid, "answer": answer, "tools": tools}

    def reset(self, sid):
        with self.lock:
            self.sessions.pop(sid, None)
        return 200, {"ok": True}


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            return host.split(":")[0] in ("127.0.0.1", "localhost") and origin in (None, f"http://{host}")

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "forbidden"})
            if self.path in FILES:
                name, ctype = FILES[self.path]
                return self._send(200, (STATIC / name).read_bytes(), ctype)
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok():
                return self._send(403, {"error": "forbidden"})
            if self.path not in ("/api/chat", "/api/reset"):
                return self._send(404, {"error": "not found"})
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self._send(415, {"error": "JSON only"})
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self._send(411, {"error": "length required"})
            if not 0 < length <= MAX_BODY:
                return self._send(413, {"error": "body too large"})
            try:
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError
            except ValueError:
                return self._send(400, {"error": "invalid JSON"})
            sid = data.get("session_id") if isinstance(data.get("session_id"), str) else None
            if self.path == "/api/reset":
                return self._send(*app.reset(sid))
            message = data.get("message")
            if not isinstance(message, str):
                return self._send(400, {"error": "message must be text"})
            self._send(*app.chat(sid, message))
    return Handler


def serve(client, port=8000):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(ChatApp(client)))
    print(f"Chat running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
