"""BM25 keyword ranking over the indexed manual chunks.

Vector search finds passages with similar meaning but can rank exact manual
terms ("air trap", "hard limit", alarm codes) too low. Hybrid retrieval fuses
both rankings with reciprocal rank fusion (RRF).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOPWORDS = frozenset(
    """a an and are as at be by can do does for from how i if in into is it its
    me my of on or the this that to was what when where which who why will with
    you your should would could about there their then than so not no""".split()
)


def _stem(token: str) -> str:
    """Light normalization so "allows"/"allow" and "limits"/"limit" match."""
    if len(token) <= 3 or token[0].isdigit():
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    return [
        _stem(token)
        for token in _TOKEN.findall(text.lower())
        if token not in _STOPWORDS and (len(token) > 1 or token.isdigit())
    ]


@dataclass
class KeywordIndex:
    """A small in-memory BM25 index; the manual has about a hundred chunks."""

    documents: list[dict[str, Any]]
    k1: float = 1.4
    b: float = 0.75

    def __post_init__(self) -> None:
        self._terms = [Counter(tokenize(doc["text"])) for doc in self.documents]
        self._lengths = [sum(terms.values()) for terms in self._terms]
        self._average = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        frequency: Counter[str] = Counter()
        for terms in self._terms:
            frequency.update(terms.keys())
        total = len(self.documents)
        self._idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in frequency.items()
        }

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """Return (document index, score) pairs, best first."""
        query_terms = set(tokenize(query))
        scores = []
        for index, terms in enumerate(self._terms):
            score = 0.0
            for term in query_terms:
                count = terms.get(term)
                if not count:
                    continue
                norm = self.k1 * (1 - self.b + self.b * self._lengths[index] / (self._average or 1))
                score += self._idf[term] * count * (self.k1 + 1) / (count + norm)
            if score > 0:
                scores.append((index, score))
        scores.sort(key=lambda item: item[1], reverse=True)
        return scores[:top_k]


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Fuse ranked ID lists; items ranked well by either list rise to the top.

    Each list's top item is placed first: a chunk that is the single best
    match by meaning or by exact terms is too strong a signal to be averaged
    away by a low rank in the other list.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    leaders = []
    for ranking in rankings:
        if ranking and ranking[0] not in leaders:
            leaders.append(ranking[0])
    leaders.sort(key=lambda item: scores[item], reverse=True)
    rest = sorted((item for item in scores if item not in leaders), key=lambda item: scores[item], reverse=True)
    return leaders + rest
