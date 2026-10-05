"""Small, dependency-free BM25 index used for the offline corpus and for sanitised internal documents.

The Azure reference deployment swaps this for Azure AI Search (``retrieval.azure_search``) behind the
same ``search`` signature.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was", "were", "will", "with", "what", "why", "how", "which", "who", "this", "these", "those", "our", "their", "your", "we", "they"]
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


@dataclass
class BM25Index:
    k1: float = 1.5
    b: float = 0.75
    _docs: list[tuple[str, Counter[str], int]] = field(default_factory=list)
    _df: Counter[str] = field(default_factory=Counter)

    def add(self, doc_id: str, text: str) -> None:
        toks = tokenize(text)
        tf = Counter(toks)
        self._docs.append((doc_id, tf, len(toks)))
        self._df.update(tf.keys())

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        if not self._docs:
            return []
        n = len(self._docs)
        avgdl = sum(d[2] for d in self._docs) / n
        q = tokenize(query)
        scores = []
        for doc_id, tf, dl in self._docs:
            s = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                s += idf * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * dl / avgdl))
            if s > 0:
                scores.append((doc_id, s))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]
