import re

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def bm25_rank(query: str, corpus: list[str]) -> list[int]:
    """Indices du corpus triés du plus au moins pertinent selon BM25 (recherche
    lexicale par mots-clés — complète la recherche vectorielle sémantique,
    notamment pour les noms propres, références, numéros exacts)."""
    if not corpus:
        return []
    bm25 = BM25Okapi([_tokenize(doc) for doc in corpus])
    scores = bm25.get_scores(_tokenize(query))
    return sorted(range(len(corpus)), key=lambda i: scores[i], reverse=True)


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Fusionne plusieurs classements (listes d'identifiants du plus au moins
    pertinent) via Reciprocal Rank Fusion — la méthode standard pour combiner
    recherche vectorielle et lexicale sans avoir à harmoniser des scores sur
    des échelles différentes (distance cosinus vs score BM25)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda item_id: scores[item_id], reverse=True)
