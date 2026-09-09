import asyncio
from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.config import settings


@lru_cache(maxsize=1)
def _get_model() -> CrossEncoder:
    # CPU volontairement : le GPU reste dedie a Ollama (LLM/embeddings/vision),
    # deja proche de sa limite de VRAM sur un laptop 8 Go. Un petit
    # cross-encoder tourne tres bien sur CPU pour reordonner ~20 candidats.
    return CrossEncoder(settings.reranker_model, device="cpu")


def _rerank_sync(query: str, documents: list[str], top_k: int) -> list[int]:
    model = _get_model()
    scores = model.predict([[query, doc] for doc in documents])
    ranked = sorted(range(len(documents)), key=lambda i: scores[i], reverse=True)
    return ranked[:top_k]


async def rerank(query: str, documents: list[str], top_k: int) -> list[int]:
    """Indices (dans `documents`) des `top_k` passages les plus pertinents
    selon un cross-encoder local — le gain de qualité le plus important d'un
    pipeline RAG standard, appliqué sur les candidats déjà présélectionnés par
    la recherche hybride plutôt que sur tout le corpus (coûteux en CPU)."""
    if not documents:
        return []
    return await asyncio.to_thread(_rerank_sync, query, documents, top_k)
