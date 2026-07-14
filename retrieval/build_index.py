"""Build (and persist) a vector index per chunker.

    python -m retrieval.build_index            # build all chunkers
    python -m retrieval.build_index fixed      # build only the baseline (Day 12)
    python -m retrieval.build_index heading parent_child   # Day 13
"""
import sys
from retrieval.corpus import load_corpus
from retrieval.chunkers import CHUNKERS
from retrieval.index import VectorIndex


def main(names: list[str]) -> None:
    names = names or list(CHUNKERS)
    unknown = [n for n in names if n not in CHUNKERS]
    if unknown:
        raise SystemExit(f"unknown chunker(s): {unknown}. choose from {list(CHUNKERS)}")
    docs = load_corpus()
    print(f"Loaded {len(docs)} docs")
    for name in names:
        chunks = CHUNKERS[name](docs)
        idx = VectorIndex.build(name, chunks)
        idx.save()
        print(f"  built '{name}': {len(chunks)} chunks -> data/indexes/{name}/")


if __name__ == "__main__":
    main(sys.argv[1:])