"""Provenance + relevance for Evidence objects (Day 19).

- source_location: a human-readable pointer to WHERE the evidence came from.
- relevance_score: how relevant the evidence is to the QUESTION, via lexical
  overlap (deterministic — never an LLM-assigned number).
"""
from __future__ import annotations
import re
from api.groundedness import overlap_fraction

# pull "ImagePullBackOff-registry" out of "[runbook: ImagePullBackOff-registry | score 0.73]"
_RUNBOOK_ID = re.compile(r"\[runbook:\s*([^\|\]]+)")

LOG_PATH = "data/logs/openstack_sandbox.log"


def derive_location(source, content: str) -> str:
    """Best-effort provenance string for a piece of evidence."""
    s = getattr(source, "value", str(source))
    if s == "metadata":
        return "postgres:runbookai/services+deployments+pods"
    if s == "logs":
        return LOG_PATH
    if s == "runbooks":
        ids = [m.strip() for m in _RUNBOOK_ID.findall(content)]
        return "runbooks/" + ",".join(ids) if ids else "runbooks/"
    return s


def compute_relevance(question: str, content: str) -> float:
    """Relevance of this evidence to the question (lexical overlap, 0.0..1.0)."""
    return round(overlap_fraction(question, content), 3)