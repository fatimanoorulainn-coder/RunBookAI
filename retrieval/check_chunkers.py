"""No-model sanity checks for the three chunkers, run against the real corpus.

    python -m retrieval.check_chunkers

Chunking is pure string manipulation, so this needs no embeddings — run it to
trust your chunkers before spending time (and model downloads) on indexing.
"""
from __future__ import annotations
from retrieval.corpus import load_corpus
from retrieval.chunkers import fixed_size, heading_aware, parent_child


def main() -> None:
    docs = load_corpus()
    doc_ids = {d.doc_id for d in docs}
    print(f"corpus: {len(docs)} docs\n")

    for name, chunks in [
        ("fixed", fixed_size(docs)),
        ("heading", heading_aware(docs)),
        ("parent_child", parent_child(docs)),
    ]:
        ids = [c.chunk_id for c in chunks]
        # 1. no empty text
        assert all(c.text.strip() for c in chunks), f"{name}: empty chunk text"
        # 2. chunk_ids are unique (they key the index + eval)
        assert len(ids) == len(set(ids)), f"{name}: duplicate chunk_id"
        # 3. every chunk traces back to a real doc
        assert all(c.doc_id in doc_ids for c in chunks), f"{name}: orphan doc_id"
        # 4. context is never smaller than the matched text
        assert all(len(c.context) >= len(c.text) for c in chunks), f"{name}: context < text"

        avg = sum(len(c.text) for c in chunks) / len(chunks)
        docs_covered = len({c.doc_id for c in chunks})
        print(f"{name:13s} {len(chunks):4d} chunks | avg_text {avg:5.0f} | "
              f"covers {docs_covered}/{len(docs)} docs | ids unique OK")

    # fixed-size specific: verify the 50-char overlap between consecutive chunks
    fx = [c for c in fixed_size(docs) if c.doc_id == docs[0].doc_id]
    if len(fx) >= 2:
        tail, head = fx[0].text[-50:], fx[1].text[:50]
        assert tail == head, "fixed: overlap tail != next head"
        print(f"\nfixed overlap check: last 50 of chunk0 == first 50 of chunk1  OK")

    print("\nall chunker checks passed")


if __name__ == "__main__":
    main()