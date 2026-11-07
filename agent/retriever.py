"""A small, dependency-free search engine for the knowledge base.

What it does better than the old "is the query a substring?" match:
- Splits text into words and ignores filler words ("how", "the", "does").
- Reduces words to a stem, so "releases", "released" and "releasing"
  all match "release".
- Knows a few synonym groups, so "how much does it cost?" finds the
  pricing entry and "when is support open?" finds the office-hours entry.
- Ranks results with BM25 (the classic relevance formula) and returns
  the best few instead of "everything that contains the text".

Honest label: this is keyword relevance + synonyms, not true embedding
based semantic search. The Retriever class has one public method
(`search`), so an embeddings version can replace it later without
touching the rest of the agent.
"""
import math
import re
from collections import Counter

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "get", "how", "i", "if", "in", "is", "it", "its", "me", "much",
    "my", "of", "on", "or", "our", "should", "so", "that", "the", "their",
    "there", "this", "to", "us", "was", "we", "what", "when", "where", "which",
    "who", "will", "with", "you", "your", "tell", "about", "any",
}

_SUFFIXES = ("ments", "ment", "ations", "ation", "ing", "ed", "es", "s")


def stem(word: str) -> str:
    """Very light stemmer. It only has to be consistent: the same function
    is applied to documents and queries, so matching forms collapse."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and not word.endswith("ss") and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def tokenize(text: str):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS and (len(w) > 1 or w.isdigit())]


_SYNONYM_GROUPS = [
    {"release", "deploy", "publish", "ship", "launch", "rollout"},
    {"hours", "open", "schedule", "availability", "time"},
    {"price", "cost", "pricing", "billing", "fee", "pay", "plan", "subscription"},
    {"password", "login", "signin", "reset", "forgot"},
    {"export", "download", "backup"},
    {"rollback", "revert", "undo"},
    {"support", "help", "contact", "assistance"},
    {"limit", "quota", "throttle", "ratelimit"},
    {"integration", "integrate", "connect", "plugin"},
    {"browser", "chrome", "firefox", "safari", "edge"},
    {"security", "vulnerability", "vulnerabilities", "exploit"},
]
_SYNONYMS = {}
for _group in _SYNONYM_GROUPS:
    _stems = {stem(w) for w in _group}
    for _s in _stems:
        _SYNONYMS.setdefault(_s, set()).update(_stems - {_s})


class Retriever:
    """BM25 ranking over a list of entries ({"id","title","content"})."""

    K1 = 1.5
    B = 0.75

    def __init__(self, entries):
        self.entries = list(entries)
        # The title is repeated so title matches count for more.
        self._docs = [
            Counter(tokenize(e["title"]) * 2 + tokenize(e["content"])) for e in self.entries
        ]
        self._lengths = [sum(d.values()) for d in self._docs]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0
        self._doc_freq = Counter()
        for doc in self._docs:
            self._doc_freq.update(doc.keys())

    def _idf(self, term: str) -> float:
        n = len(self.entries)
        df = self._doc_freq.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _score(self, doc_index: int, weighted_terms) -> float:
        doc = self._docs[doc_index]
        length = self._lengths[doc_index] or 1
        score = 0.0
        for term, weight in weighted_terms.items():
            tf = doc.get(term, 0)
            if not tf:
                continue
            norm = tf + self.K1 * (1 - self.B + self.B * length / (self._avg_len or 1))
            score += weight * self._idf(term) * tf * (self.K1 + 1) / norm
        return score

    def search(self, query: str, k: int = 3):
        """Return up to k entries, best first. Empty list if nothing matches."""
        terms = tokenize(query)
        if not terms or not self.entries:
            return []
        weighted = {}
        for t in terms:
            weighted[t] = 1.0
        for t in terms:  # synonyms count for half as much as the words typed
            for syn in _SYNONYMS.get(t, ()):
                weighted.setdefault(syn, 0.5)

        scored = [(self._score(i, weighted), i) for i in range(len(self.entries))]
        scored = [s for s in scored if s[0] > 0]
        if not scored:
            return []
        scored.sort(key=lambda s: s[0], reverse=True)
        best = scored[0][0]
        keep = [s for s in scored if s[0] >= 0.35 * best][:k]
        return [self.entries[i] for _, i in keep]
