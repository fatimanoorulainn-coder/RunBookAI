"""Lexical-overlap utilities: groundedness .

check_groundedness: fraction of root_cause content-words present in the evidence.
overlap_fraction:   shared primitive — fraction of `query` content-words in `target`.

IMPORTANT: this is approximate LEXICAL OVERLAP, not NLI entailment. It detects
word-level divergence, NOT semantic contradiction — "caused by X" and "NOT caused
by X" score identically. A cheap smoke alarm, not proof of correctness.
"""
from __future__ import annotations
import re

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "for", "and", "or", "but", "with", "as",
    "by", "from", "that", "this", "it", "its", "due", "because", "caused",
    "cause", "root", "there", "has", "have", "had", "not", "no", "which",
    "why", "what", "when", "where", "how",
    "service", "services", "pod", "pods", "deployment", "deployments",
}
_TOKEN = re.compile(r"[a-z0-9]+")


def _content_words(text: str) -> set[str]:
    out = set()
    for w in _TOKEN.findall(text.lower()):
        if len(w) < 2 or w in _STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]              # light plural normalization
        out.add(w)
    return out


def overlap_fraction(query: str, target: str) -> float:
    """Fraction of query content-words that appear in target. 0.0..1.0."""
    q = _content_words(query)
    if not q:
        return 0.0
    return len(q & _content_words(target)) / len(q)


def check_groundedness(root_cause: str, evidence_texts: list[str]) -> float:
    """How much of the root_cause is anchored in the evidence."""
    return overlap_fraction(root_cause, " ".join(evidence_texts))