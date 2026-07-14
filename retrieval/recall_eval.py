"""Recall@K across all three chunkers (Day 14).

Metric = DOC-level recall: a question is a hit if any of the top-K retrieved
chunks belongs to an expected doc_id. Doc-level (not chunk-level) because each
chunker emits different chunk_ids, so only doc membership is comparable across
strategies.

    python -m retrieval.build_index          # build all three indexes first
    python -m retrieval.recall_eval
"""
from __future__ import annotations
import json
from pathlib import Path
from retrieval.index import VectorIndex

QUESTIONS = Path(__file__).resolve().parents[1] / "evals" / "retrieval_questions.json"
CHUNKERS = ("fixed", "heading", "parent_child")
KS = (1, 3, 5)


def recall_at_k(index: VectorIndex, questions: list[dict], k: int) -> float:
    hits = 0
    for item in questions:
        got = {c.doc_id for c, _ in index.search(item["q"], k)}
        if got & set(item["docs"]):
            hits += 1
    return hits / len(questions)


def main() -> None:
    questions = json.loads(QUESTIONS.read_text("utf-8"))
    print(f"{len(questions)} questions\n")
    header = "chunker".ljust(16) + "".join(f"R@{k}".rjust(9) for k in KS)
    print(header)
    print("-" * len(header))
    for name in CHUNKERS:
        idx = VectorIndex.load(name)                 # load once
        scores = [recall_at_k(idx, questions, k) for k in KS]
        row = name.ljust(16) + "".join(f"{s:8.2%} " for s in scores)
        print(row)


if __name__ == "__main__":
    main()