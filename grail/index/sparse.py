"""BM25 sparse retrieval. Legal terms of art are exact strings, so lexical
matching matters as much as dense similarity (roadmap: hybrid BM25 + dense)."""
from __future__ import annotations
import re

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25:
    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        try:
            from rank_bm25 import BM25Okapi
            self._impl = BM25Okapi(corpus_tokens, k1=k1, b=b)
            self._native = True
        except Exception:  # noqa: BLE001 - tiny fallback so we never hard-depend
            self._impl = _MiniBM25(corpus_tokens, k1=k1, b=b)
            self._native = False

    def scores(self, query: str):
        return self._impl.get_scores(tokenize(query))


class _MiniBM25:
    """Dependency-free BM25 fallback (Okapi)."""
    def __init__(self, corpus, k1=1.5, b=0.75):
        import math
        self.k1, self.b = k1, b
        self.corpus = corpus
        self.N = len(corpus)
        self.doclen = [len(d) for d in corpus]
        self.avgdl = sum(self.doclen) / max(self.N, 1)
        self.df: dict[str, int] = {}
        self.tf: list[dict[str, int]] = []
        for d in corpus:
            freqs: dict[str, int] = {}
            for w in d:
                freqs[w] = freqs.get(w, 0) + 1
            self.tf.append(freqs)
            for w in freqs:
                self.df[w] = self.df.get(w, 0) + 1
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5))
                    for w, n in self.df.items()}

    def get_scores(self, query):
        scores = [0.0] * self.N
        for i in range(self.N):
            dl = self.doclen[i]
            for w in query:
                if w not in self.tf[i]:
                    continue
                f = self.tf[i][w]
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += self.idf.get(w, 0.0) * f * (self.k1 + 1) / denom
        return scores
