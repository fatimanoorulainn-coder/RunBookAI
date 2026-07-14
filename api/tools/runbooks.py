"""SRE runbook search (Day 15) — semantic search over the runbook corpus.

Returns "" (not a 'no match' sentence) when the best hit is weak, so your
Day-9 empty-evidence filter treats an irrelevant search as no evidence rather
than fake evidence. 'heading' is the chunker chosen by the Day-14 Recall@K eval.
"""
from functools import lru_cache
from retrieval.index import VectorIndex

_ACTIVE_INDEX = "heading"   # winner of the Day-14 evaluation
_MIN_SCORE = 0.30           # below this the top hit isn't relevant enough to count
_TOP_K = 3


@lru_cache(maxsize=1)
def _index() -> VectorIndex:
    return VectorIndex.load(_ACTIVE_INDEX)


def search_runbooks(query: str, k: int = _TOP_K) -> str:
    """Semantic search over runbooks. Returns formatted context, or '' when
    nothing is relevant enough (so it counts as no evidence)."""
    hits = _index().search(query, k)
    kept = [(c, s) for c, s in hits if s >= _MIN_SCORE]
    if not kept:
        return ""
    blocks = [f"[runbook: {c.doc_id} | score {s:.2f}]\n{c.context.strip()}"
              for c, s in kept]
    return "\n\n---\n\n".join(blocks)