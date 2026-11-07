import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from agent import tools
from agent.retriever import Retriever, stem
from agent.tools import calculator, lookup_knowledge_base


def ids(query):
    result = lookup_knowledge_base(query)
    try:
        return [r["id"] for r in json.loads(result)]
    except json.JSONDecodeError:
        return []


class CalculatorTests(unittest.TestCase):
    def test_normal_math(self):
        self.assertEqual(calculator("42 * 17 - 100"), "614")
        self.assertEqual(calculator("-5 + 2"), "-3")
        self.assertEqual(calculator("10 / 4"), "2.5")
        self.assertEqual(calculator("2 ** 10"), "1024")

    def test_blocks_code_execution(self):
        for bad in ["__import__('os').system('ls')", "abs(-1)", "(1).__class__", "hello", "x + 1"]:
            self.assertIn("error", calculator(bad), bad)

    def test_blocks_denial_of_service(self):
        start = time.time()
        for bad in ["9**9**9**9", "2**101", "(9**99)**99", "10**301", "1e999 * 10"]:
            self.assertIn("error", calculator(bad), bad)
        self.assertLess(time.time() - start, 1.0)

    def test_allows_big_but_reasonable(self):
        self.assertTrue(calculator("10**100").startswith("1000"))

    def test_division_by_zero_and_long_input(self):
        self.assertIn("error", calculator("1/0"))
        self.assertIn("error", calculator("1+" * 150 + "1"))


class SearchTests(unittest.TestCase):
    def test_stemming_collapses_forms(self):
        self.assertEqual(stem("releases"), stem("release"))
        self.assertEqual(stem("published"), stem("publish"))
        self.assertEqual(stem("deployment"), stem("deploys"))

    def test_finds_the_right_entry(self):
        self.assertEqual(ids("How do Taskboard releases get published?")[0], "kb-001")
        self.assertEqual(ids("suspicious entry")[0], "kb-003")
        self.assertEqual(ids("is internet explorer supported")[0], "kb-011")
        self.assertEqual(ids("429 too many requests")[0], "kb-008")

    def test_understands_different_wording(self):
        # None of these share the exact words used in the entries.
        self.assertEqual(ids("how much does it cost")[0], "kb-007")
        self.assertEqual(ids("when is support open")[0], "kb-002")
        self.assertEqual(ids("I forgot my login")[0], "kb-006")
        self.assertEqual(ids("how do I download my data")[0], "kb-009")

    def test_no_match_message(self):
        self.assertIn("No public knowledge base entries", lookup_knowledge_base("weather in Paris"))
        self.assertIn("No public knowledge base entries", lookup_knowledge_base("   "))

    def test_internal_entries_never_leak(self):
        for q in ["credentials", "Infrastructure credentials index", "internal", "kb-004",
                  "escalation rota on-call", "refund approval limits", "INTERNAL-ONLY-MARKER"]:
            result = lookup_knowledge_base(q)
            self.assertNotIn("INTERNAL-ONLY", result, q)
            self.assertNotIn("Infrastructure credentials index", result, q)
            self.assertNotIn("kb-004", result, q)
            self.assertNotIn("kb-013", result, q)
            self.assertNotIn("kb-014", result, q)

    def test_entry_without_access_field_is_not_public(self):
        entries = [
            {"id": "x1", "title": "Open thing", "content": "visible words", "access": "public"},
            {"id": "x2", "title": "No label", "content": "visible words too"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kb.json"
            path.write_text(json.dumps(entries))
            with mock.patch.object(tools, "KB_PATH", path):
                found = json.loads(lookup_knowledge_base("visible words"))
        self.assertEqual([r["id"] for r in found], ["x1"])

    def test_retriever_handles_empty_corpus(self):
        self.assertEqual(Retriever([]).search("anything"), [])


if __name__ == "__main__":
    unittest.main()
