"""Tools the agent is allowed to call.

Both tools enforce their own limits in code — the agent (and the model
behind it) never gets to decide what it's allowed to touch. That's the
point: least-privilege isn't a prompt instruction, it's a boundary the
code enforces regardless of what the model is told to do.
"""
import ast
import json
import operator
from pathlib import Path

KB_PATH = Path(__file__).parent / "knowledge_base.json"

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("expression not allowed")


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression. No names, calls, or
    attribute access are permitted — only numbers and + - * / ** ()."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception:
        return "error: could not evaluate that expression"


def lookup_knowledge_base(query: str) -> str:
    """Search the knowledge base for entries whose title or content
    contains the query text. Only entries tagged 'public' are ever
    eligible — this filter happens here, in code, before anything is
    assembled into a response, not as an instruction to the model."""
    entries = json.loads(KB_PATH.read_text())
    query_lower = query.lower()
    matches = [
        e for e in entries
        if e["access"] == "public"
        and (query_lower in e["title"].lower() or query_lower in e["content"].lower())
    ]
    if not matches:
        return "No public knowledge base entries matched that query."
    return json.dumps([{"title": m["title"], "content": m["content"]} for m in matches])
