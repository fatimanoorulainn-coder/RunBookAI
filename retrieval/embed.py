"""Local embeddings via sentence-transformers. No API key, no rate limit."""
from __future__ import annotations
import numpy as np

_MODEL_NAME = "all-MiniLM-L6-v2"   # 384-dim, fast, CPU-friendly
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Return L2-normalized float32 matrix (n, 384) so dot == cosine."""
    m = _get_model()
    vecs = m.encode(texts, batch_size=batch_size, show_progress_bar=len(texts) > 200,
                    convert_to_numpy=True, normalize_embeddings=True)
    return vecs.astype("float32")