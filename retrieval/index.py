"""Brute-force cosine index over ~hundreds-to-thousands of chunks.

At this scale numpy dot-product is instant and fully transparent, which keeps
the Recall@K comparison honest. Swap for FAISS/pgvector only if the corpus grows.
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from dataclasses import asdict
from retrieval.chunkers import Chunk
from retrieval.embed import embed

INDEX_DIR = Path(__file__).resolve().parents[1] / "data" / "indexes"


class VectorIndex:
    def __init__(self, name: str, vectors: np.ndarray, chunks: list[Chunk]):
        self.name = name
        self.vectors = vectors           # (n, d), rows L2-normalized
        self.chunks = chunks

    @classmethod
    def build(cls, name: str, chunks: list[Chunk]) -> "VectorIndex":
        vectors = embed([c.text for c in chunks])
        return cls(name, vectors, chunks)

    def search(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        q = embed([query])[0]                      # (d,)
        scores = self.vectors @ q                  # cosine, since all normalized
        top = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in top]

    def save(self, index_dir: Path = INDEX_DIR) -> None:
        d = index_dir / self.name
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "vectors.npy", self.vectors)
        (d / "chunks.json").write_text(
            json.dumps([asdict(c) for c in self.chunks]), encoding="utf-8")

    @classmethod
    def load(cls, name: str, index_dir: Path = INDEX_DIR) -> "VectorIndex":
        d = index_dir / name
        vectors = np.load(d / "vectors.npy")
        chunks = [Chunk(**c) for c in json.loads((d / "chunks.json").read_text("utf-8"))]
        return cls(name, vectors, chunks)