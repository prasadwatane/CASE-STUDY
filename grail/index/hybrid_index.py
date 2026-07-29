"""Hybrid index over legal units: dense (bge-small) + BM25, fused with RRF.

Build once, persist to disk, load at eval time. Reciprocal Rank Fusion avoids
having to calibrate a score-scale between the two retrievers.
"""
from __future__ import annotations
import os
import pickle

import numpy as np

from config import INDEX_DIR, RRF_K, CANDIDATE_K
from grail.ingest.schema import LegalUnit
from grail.index.embedder import get_embedder
from grail.index.sparse import BM25, tokenize


class HybridIndex:
    def __init__(self, units: list[LegalUnit], embeddings: np.ndarray,
                 backend: str):
        self.units = units
        self.embeddings = embeddings
        self.backend = backend
        self.bm25 = BM25([tokenize(u.text) for u in units])
        self._embedder = None            # lazily loaded + cached for queries

    def _emb(self):
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    # --- build / persist ----------------------------------------------------
    @classmethod
    def build(cls, units: list[LegalUnit]) -> "HybridIndex":
        emb = get_embedder()
        vecs = emb.encode([u.text for u in units], is_query=False)
        idx = cls(units, vecs, emb.backend)
        idx._embedder = emb
        return idx

    def save(self, path: str = INDEX_DIR) -> None:
        os.makedirs(path, exist_ok=True)
        np.save(os.path.join(path, "embeddings.npy"), self.embeddings)
        with open(os.path.join(path, "units.pkl"), "wb") as fh:
            pickle.dump(self.units, fh)
        with open(os.path.join(path, "meta.pkl"), "wb") as fh:
            pickle.dump({"backend": self.backend}, fh)

    @classmethod
    def load(cls, path: str = INDEX_DIR) -> "HybridIndex":
        embs = np.load(os.path.join(path, "embeddings.npy"))
        with open(os.path.join(path, "units.pkl"), "rb") as fh:
            units = pickle.load(fh)
        with open(os.path.join(path, "meta.pkl"), "rb") as fh:
            backend = pickle.load(fh)["backend"]
        return cls(units, embs, backend)

    # --- search -------------------------------------------------------------
    def _dense_ranks(self, query: str) -> list[int]:
        q = self._emb().encode([query], is_query=True)[0]
        sims = self.embeddings @ q
        return list(np.argsort(-sims)[:CANDIDATE_K])

    def _sparse_ranks(self, query: str) -> list[int]:
        scores = np.asarray(self.bm25.scores(query))
        return list(np.argsort(-scores)[:CANDIDATE_K])

    def search(self, query: str, allowed_idx: set[int] | None = None):
        """Return list[(idx, rrf_score)] fused from dense + sparse."""
        dense = self._dense_ranks(query)
        sparse = self._sparse_ranks(query)
        fused: dict[int, float] = {}
        for ranks in (dense, sparse):
            for rank, idx in enumerate(ranks):
                if allowed_idx is not None and idx not in allowed_idx:
                    continue
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)
        return sorted(fused.items(), key=lambda kv: -kv[1])
