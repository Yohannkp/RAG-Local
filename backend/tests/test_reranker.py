import pytest

from app.core.reranker import rerank


@pytest.mark.asyncio
async def test_rerank_orders_by_relevance_to_query():
    documents = [
        "Le chat dort sur le canapé toute la journée.",
        "Le plafond de remboursement pour un repas d'affaires est de 60 euros.",
        "Les chiens aiment jouer dans le jardin.",
    ]
    top = await rerank("Quel est le plafond de remboursement des repas ?", documents, top_k=1)
    assert top == [1]


@pytest.mark.asyncio
async def test_rerank_empty_documents():
    assert await rerank("peu importe", [], top_k=5) == []
