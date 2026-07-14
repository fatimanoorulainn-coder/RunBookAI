"""Manually inspect what an index retrieves. Useful for the Day-12 smoke test
and for eyeballing retrieval quality on Day 15.

    python -m retrieval.query fixed "pod can't pull its image from the registry"
"""
import sys
from retrieval.index import VectorIndex


def main(index_name: str, query: str, k: int = 5) -> None:
    idx = VectorIndex.load(index_name)
    print(f"index='{index_name}'  query={query!r}\n")
    for rank, (chunk, score) in enumerate(idx.search(query, k), 1):
        preview = " ".join(chunk.text.split())[:160]
        print(f"{rank}. {score:.3f}  {chunk.doc_id}")
        print(f"     {preview}...\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit('usage: python -m retrieval.query <index_name> "<query>"')
    main(sys.argv[1], sys.argv[2])