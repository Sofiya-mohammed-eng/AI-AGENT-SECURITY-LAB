import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from agent.logger import AgentLogger
from tests.fakes import FakeClient, FakeMessage, tool_call
from web.server import ChatApp, make_handler


class WebTests(unittest.TestCase):
    def start(self, script):
        app = ChatApp(FakeClient(script), AgentLogger(enabled=False))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        h = {"Content-Type": "application/json"} if body is not None else {}
        h.update(headers or {})
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        return r.status, dict(r.getheaders()), r.read()

    def test_page_and_security_headers(self):
        self.start([])
        status, headers, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Taskboard Support Agent", body)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(self.call("GET", "/etc/passwd")[0], 404)

    def test_chat_and_flagged_tool(self):
        self.start([
            FakeMessage(tool_calls=[tool_call("1", "lookup_knowledge_base", '{"query":"suspicious entry"}')]),
            FakeMessage(content="Ignored the injection."),
        ])
        status, _, body = self.call("POST", "/api/chat", json.dumps({"message": "look it up"}))
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data["answer"], "Ignored the injection.")
        self.assertTrue(data["tools"][0]["flagged"])
        self.assertTrue(data["session_id"])

    def test_rejects_bad_requests(self):
        self.start([])
        msg = json.dumps({"message": "hi"})
        self.assertEqual(self.call("POST", "/api/chat", msg, {"Host": "evil.com"})[0], 403)
        self.assertEqual(self.call("POST", "/api/chat", msg, {"Origin": "http://evil.com"})[0], 403)
        self.assertEqual(self.call("POST", "/api/chat", msg, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.call("POST", "/api/chat", "x" * 9000)[0], 413)
        self.assertEqual(self.call("POST", "/api/chat", "not json")[0], 400)
        self.assertEqual(self.call("POST", "/api/chat", json.dumps({"message": 5}))[0], 400)

    def test_empty_message_is_an_answer_not_a_crash(self):
        self.start([])
        status, _, body = self.call("POST", "/api/chat", json.dumps({"message": " "}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["answer"].startswith("error"))


if __name__ == "__main__":
    unittest.main()
