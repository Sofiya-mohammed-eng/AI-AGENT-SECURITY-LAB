"""Tools the agent is allowed to call.

Both tools enforce their own limits in code — the agent (and the model
behind it) never gets to decide what it's allowed to touch. That's the
point: least-privilege isn't a prompt instruction, it's a boundary the
code enforces regardless of what the model is told to do.
"""
import ast
import json
import math
import operator
from pathlib import Path

from .retriever import Retriever

KB_PATH = Path(__file__).parent / "knowledge_base.json"

# Calculator limits: these stop "denial of service" inputs like 9**9**9**9.
MAX_EXPRESSION_CHARS = 200
MAX_EXPONENT = 100
MAX_RESULT_LOG10 = 300  # results above ~1e300 are refused

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _check_pow(base, exponent):
    if abs(exponent) > MAX_EXPONENT:
        raise ValueError("exponent too large")
    if base != 0 and abs(exponent) * math.log10(abs(base)) > MAX_RESULT_LOG10:
        raise ValueError("result too large")


def _safe_eval(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        if isinstance(node.value, float) and not math.isfinite(node.value):
            raise ValueError("number not allowed")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Pow):
            _check_pow(left, right)  # check BEFORE computing
        return _ALLOWED_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("expression not allowed")


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression. No names, calls, or
    attribute access are permitted — only numbers and + - * / ** ().
    Length, exponent and result size are capped."""
    try:
        if len(expression) > MAX_EXPRESSION_CHARS:
            raise ValueError("expression too long")
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        if isinstance(result, float) and not math.isfinite(result):
            raise ValueError("result not finite")
        return str(result)
    except Exception:
        return "error: could not evaluate that expression"


def _load_public_entries():
    """Load the knowledge base and keep ONLY public entries. Internal
    entries are dropped here, before any search index is built, so they
    can never be ranked, matched or returned. An entry with a missing
    'access' field is treated as not public."""
    entries = json.loads(KB_PATH.read_text())
    return [e for e in entries if e.get("access") == "public"]


def lookup_knowledge_base(query: str) -> str:
    """Search the public knowledge base and return the best matches
    (up to 3), ranked by relevance. See retriever.py for how ranking works."""
    results = Retriever(_load_public_entries()).search(query, k=3)
    if not results:
        return "No public knowledge base entries matched that query."
    return json.dumps(
        [{"id": r["id"], "title": r["title"], "content": r["content"]} for r in results]
    )
