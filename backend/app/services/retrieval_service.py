from collections.abc import AsyncIterator

from app.config import settings
from app.core import vector_store
from app.core.ollama_client import ollama_client
from app.models.schemas import ChatMessage, SourceOut

SYSTEM_PROMPT = """Tu es un assistant qui répond UNIQUEMENT à partir des extraits de \
documents fournis ci-dessous, numérotés [1], [2], etc.

Règles strictes :
- Cite tes affirmations avec le numéro de la source entre crochets, ex: "Le contrat \
expire en 2025 [2]."
- Si l'information demandée n'apparaît pas dans les extraits fournis, réponds \
explicitement que tu ne trouves pas la réponse dans les documents fournis. \
N'invente jamais d'information.
- Réponds dans la langue de la question.

Extraits disponibles :
{context}
"""


def _build_context_block(sources: list[SourceOut], hits_text: list[str]) -> str:
    blocks = []
    for src, text in zip(sources, hits_text):
        label = (
            f"{src.filename}, p.{src.page_number}"
            if src.page_number is not None
            else (
                f"{src.filename}, section « {src.section_title} »"
                if src.section_title
                else src.filename
            )
        )
        blocks.append(f"[{src.index}] ({label}):\n{text}")
    return "\n\n".join(blocks) if blocks else "(aucun extrait pertinent trouvé)"


async def stream_answer(
    message: str, doc_ids: list[str], history: list[ChatMessage]
) -> AsyncIterator[tuple[str, object]]:
    if not doc_ids:
        yield ("sources", [])
        yield (
            "token",
            "Sélectionne au moins un document dans la bibliothèque avant de "
            "poser une question.",
        )
        yield ("done", None)
        return

    query_embedding_list = await ollama_client.embed([message])
    query_embedding = query_embedding_list[0]
    hits = vector_store.query(query_embedding, doc_ids, top_k=settings.top_k)

    sources: list[SourceOut] = []
    hits_text: list[str] = []
    for i, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        sources.append(
            SourceOut(
                index=i,
                doc_id=meta.get("doc_id", ""),
                filename=meta.get("filename", ""),
                page_number=meta.get("page_number"),
                section_title=meta.get("section_title"),
                snippet=hit["text"][:400],
            )
        )
        hits_text.append(hit["text"])

    context = _build_context_block(sources, hits_text)
    system_message = {"role": "system", "content": SYSTEM_PROMPT.format(context=context)}
    messages = (
        [system_message]
        + [{"role": h.role, "content": h.content} for h in history]
        + [{"role": "user", "content": message}]
    )

    yield ("sources", sources)
    async for token in ollama_client.chat_stream(messages):
        yield ("token", token)
    yield ("done", None)
