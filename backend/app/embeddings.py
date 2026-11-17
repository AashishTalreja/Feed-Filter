"""
Wraps the Hugging Face sentence-transformers model used to embed video text
and category anchors. Loaded lazily as a singleton so the model is only
pulled into memory once per process.

Falls back to a deterministic hashing-based pseudo-embedding if the real
model can't be downloaded (e.g. no network access to huggingface.co in a
sandboxed/offline environment). This keeps the rest of the pipeline
testable end-to-end without a live model, but it is NOT a semantic
embedding — swap in real internet access before relying on it for
classification quality.
"""

import hashlib
import logging

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_load_failed = False


def _load_model():
    global _model, _model_load_failed
    if _model is not None or _model_load_failed:
        return
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model_name)
        logger.info("Loaded embedding model %s", settings.embedding_model_name)
    except Exception as exc:  # noqa: BLE001 - want to degrade gracefully, not crash
        _model_load_failed = True
        logger.warning(
            "Could not load %s (%s). Falling back to hashing pseudo-embeddings — "
            "classification quality will be degraded until real network/model "
            "access is available.",
            settings.embedding_model_name,
            exc,
        )


def _hashing_fallback_embedding(text: str) -> np.ndarray:
    """Deterministic, dependency-free stand-in so the pipeline still runs
    offline. Buckets token hashes into a fixed-size vector (a crude
    feature-hashing trick) — nowhere near as good as a real sentence
    embedding, but keeps cosine similarity meaningful enough for smoke
    testing the rest of the system."""
    dim = settings.embedding_dim
    vec = np.zeros(dim, dtype=np.float32)
    tokens = text.lower().split()
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def embed(text: str) -> list[float]:
    _load_model()
    if _model is not None:
        vector = _model.encode(text, normalize_embeddings=True)
        return vector.tolist()
    return _hashing_fallback_embedding(text).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1e-8
    return float(np.dot(va, vb) / denom)


def is_using_real_model() -> bool:
    _load_model()
    return _model is not None
