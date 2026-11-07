"""Local audit log: one JSON object per line in logs/agent.jsonl.

Records what the agent was asked, which tools it called (with arguments),
whether a tool result was flagged as a possible injection, and what it
answered. API keys are scrubbed from everything before it is written, and
a logging failure never crashes the agent.

Turn off with:  export AGENT_LOG=off
Change the file: export AGENT_LOG_PATH=/some/where/agent.jsonl
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .guards import redact_secrets

DEFAULT_LOG_PATH = "logs/agent.jsonl"


def _redact_obj(value):
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {k: _redact_obj(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_obj(v) for v in value]
    return value


class AgentLogger:
    def __init__(self, path=None, enabled=None):
        self.path = Path(path or os.environ.get("AGENT_LOG_PATH", DEFAULT_LOG_PATH))
        if enabled is None:
            enabled = os.environ.get("AGENT_LOG", "on").lower() != "off"
        self.enabled = enabled

    def log(self, event: str, **fields):
        if not self.enabled:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event,
            **_redact_obj(fields),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass  # logging must never break the agent


_default_logger = None


def get_default_logger() -> AgentLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = AgentLogger()
    return _default_logger


def read_logs(path=None, last: int = 20):
    """Return the last `last` log records as a list of dicts."""
    p = Path(path or os.environ.get("AGENT_LOG_PATH", DEFAULT_LOG_PATH))
    if not p.exists():
        return []
    records = []
    for line in p.read_text(encoding="utf-8").splitlines()[-last:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
