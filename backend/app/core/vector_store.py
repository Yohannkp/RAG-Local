from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

_client = chromadb.PersistentClient(
    path=str(settings.chroma_dir),
    settings=ChromaSettings(anonymized_telemetry=False),
)


def get_or_create_collection(name: str):
    """Retourne une collection persistante ne recourant pas au fallback
    d'embedder auto de Chroma."""
    return _client.get_or_create_collection(name=name, embedding_function=None)


# embedding_function=None: embeddings are always supplied explicitly by the
# ingestion/retrieval services (via Ollama). This guarantees Chroma never falls
# back to auto-downloading its default ONNX embedding model from Hugging Face,
# which would silently break the "nothing ever leaves/downloads to the machine
# at query time" privacy guarantee.
_collection = get_or_create_collection("documents")


def local_collection():
    return get_or_create_collection("local_files")


def reset_local_collection():
    """Vide l'index des fichiers locaux (changement de format d'index)."""
    try:
        _client.delete_collection("local_files")
    except Exception:
        pass
    return get_or_create_collection("local_files")


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
    ids = result.get("ids") or [[]]
    documents = result.get("documents") or [[]]
    metadatas = result.get("metadatas") or [[]]
    distances = result.get("distances") or [[]]
    for chunk_id, text, meta, dist in zip(ids[0], documents[0], metadatas[0], distances[0]):
        hits.append({"id": chunk_id, "text": text, "metadata": meta, "distance": dist})
    return hits


def get_all_chunks(doc_ids: list[str]) -> list[dict[str, Any]]:
    """Tous les chunks des documents selectionnes, sans recherche par similarite.
    Sert de corpus pour le classement lexical BM25 (recherche hybride)."""
    if not doc_ids:
        return []
    result = _collection.get(
        where={"doc_id": {"$in": doc_ids}}, include=["documents", "metadatas"]
    )
    chunks: list[dict[str, Any]] = []
    for chunk_id, text, meta in zip(
        result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or []
    ):
        chunks.append({"id": chunk_id, "text": text, "metadata": meta})
    return chunks


def delete_by_doc_id(doc_id: str) -> None:
    _collection.delete(where={"doc_id": doc_id})
