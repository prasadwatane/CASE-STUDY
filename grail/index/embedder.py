"""Dense embeddings.

Real backend: bge-small-en-v1.5 via sentence-transformers (roadmap). If that is
unavailable (offline CI / no download), fall back to a deterministic hashing
embedding so the whole pipeline still runs and tests pass. The hashing vector is
lexical, not semantic — good enough to exercise the architecture, not a
substitute for bge-small in the real audit. Switch via config.EMBED_BACKEND.

Note on bge models: for short query -> passage retrieval, the QUERY must be
prefixed with an instruction; passages are embedded raw. Skipping this prefix
noticeably degrades retrieval quality, which is why encode() takes is_query.
"""
from __future__ import annotations
import hashlib
import re

import numpy as np

from config import EMBED_BACKEND, EMBED_MODEL, EMBED_DIM_FALLBACK

_TOKEN = re.compile(r"[a-z0-9]+")

# Recommended bge-en-v1.5 retrieval instruction (applied to queries only).
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class _HashingEmbedder:
    backend = "hashing"

    def __init__(self, dim: int = EMBED_DIM_FALLBACK):
        self.dim = dim

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in _TOKEN.findall(t.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vecs[i, h % self.dim] += 1.0
            n = np.linalg.norm(vecs[i])
            if n > 0:
                vecs[i] /= n
        return vecs


class _SbertEmbedder:
    backend = "sbert"

    def __init__(self, model_name: str = EMBED_MODEL):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        try:
            self.dim = self.model.get_embedding_dimension()
        except AttributeError:                       # older API
            self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        if is_query:
            texts = [BGE_QUERY_PREFIX + t for t in texts]
        return np.asarray(
            self.model.encode(texts, normalize_embeddings=True,
                              show_progress_bar=False),
            dtype=np.float32)


def get_embedder():
    choice = EMBED_BACKEND
    if choice in ("auto", "sbert"):
        try:
            return _SbertEmbedder()
        except Exception as exc:  # noqa: BLE001
            if choice == "sbert":
                raise
            print(f"[embedder] sbert unavailable ({exc.__class__.__name__}); "
                  f"falling back to hashing backend.")
    return _HashingEmbedder()
