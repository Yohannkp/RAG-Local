from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

_client = chromadb.PersistentClient(
    path=str(settings.chroma_dir),
    settings=ChromaSettings(anonymized_telemetry=False),
)

# embedding_function=None: embeddings are always supplied explicitly by the
# ingestion/retrieval services (via Ollama). This guarantees Chroma never falls
# back to auto-downloading its default ONNX embedding model from Hugging Face,
# which would silently break the "nothing ever leaves/downloads to the machine
# at query time" privacy guarantee.
_collection = _client.get_or_create_collection(
    name="documents", embedding_function=None
)


def add_chunks(
    doc_id: str,
    texts: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> None:
    ids = [f"{doc_id}_{i}" for i in range(len(texts))]
    _collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def query(
    query_embedding: list[float], doc_ids: list[str], top_k: int
) -> list[dict[str, Any]]:
    where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
    result = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict[str, Any]] = []
    documents = result.get("documents") or [[]]
    metadatas = result.get("metadatas") or [[]]
    distances = result.get("distances") or [[]]
    for text, meta, dist in zip(documents[0], metadatas[0], distances[0]):
        hits.append({"text": text, "metadata": meta, "distance": dist})
    return hits


def delete_by_doc_id(doc_id: str) -> None:
    _collection.delete(where={"doc_id": doc_id})
