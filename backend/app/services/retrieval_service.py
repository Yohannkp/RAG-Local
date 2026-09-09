from collections.abc import AsyncIterator

from app.config import settings
from app.core import db, vector_store
from app.core.ollama_client import ollama_client
from app.core.reranker import rerank
from app.models.schemas import ChatMessage, SourceOut
from app.services.hybrid_search import bm25_rank, reciprocal_rank_fusion

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

REWRITE_PROMPT = """Voici l'historique d'une conversation, suivi d'une nouvelle \
question qui peut faire référence au contexte précédent (ex: "et pour la page 3 ?", \
"et lui ?", "détaille le deuxième point").

Reformule cette question en une question autonome et complète, compréhensible sans \
le reste de la conversation, dans la même langue. Si elle est déjà autonome, \
renvoie-la telle quelle. Réponds UNIQUEMENT avec la question reformulée, sans \
aucune explication ni guillemets.

Historique :
{history}

Question à reformuler : {question}

Question reformulée :"""


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


async def _rewrite_query(question: str, history: list[ChatMessage]) -> str:
    """Condense (question, historique) en une question autonome avant la
    recherche — sinon un suivi de conversation comme "et pour la page 3 ?"
    n'a presque aucune chance d'être bien retrouvé par la recherche."""
    if not history:
        return question
    history_text = "\n".join(f"{h.role}: {h.content}" for h in history[-6:])
    prompt = REWRITE_PROMPT.format(history=history_text, question=question)
    rewritten = ""
    async for chunk in ollama_client.chat_stream(
        [{"role": "user", "content": prompt}], num_ctx=4096
    ):
        rewritten += chunk
    rewritten = rewritten.strip().strip('"')
    return rewritten or question


async def _hybrid_search(query: str, doc_ids: list[str]) -> list[dict]:
    """Recherche hybride : fusionne un classement vectoriel (sémantique) et un
    classement BM25 (lexical, mots-clés exacts) via Reciprocal Rank Fusion,
    puis affine avec un cross-encoder. Chaque étape gère un défaut de l'autre :
    le vectoriel rate parfois des références/numéros exacts que BM25 attrape,
    le reranking corrige les cas où la similarité d'embedding seule trompe."""
    all_chunks = vector_store.get_all_chunks(doc_ids)
    if not all_chunks:
        return []

    query_embedding = (await ollama_client.embed([query]))[0]
    n_candidates = min(settings.hybrid_candidates, len(all_chunks))
    vector_hits = vector_store.query(query_embedding, doc_ids, top_k=n_candidates)
    vector_ranking = [h["id"] for h in vector_hits]

    bm25_order = bm25_rank(query, [c["text"] for c in all_chunks])
    bm25_ranking = [all_chunks[i]["id"] for i in bm25_order[:n_candidates]]

    fused_ids = reciprocal_rank_fusion([vector_ranking, bm25_ranking])
    by_id = {c["id"]: c for c in all_chunks}
    candidates = [by_id[i] for i in fused_ids if i in by_id][: settings.hybrid_candidates]

    reranked_idx = await rerank(query, [c["text"] for c in candidates], settings.top_k)
    return [candidates[i] for i in reranked_idx]


async def stream_answer(
    message: str, doc_ids: list[str], history: list[ChatMessage]
) -> AsyncIterator[tuple[str, object]]:
    # Aucune sélection manuelle = chercher dans toute la bibliothèque plutôt
    # que de forcer l'utilisateur à cocher des cases à chaque question — la
    # recherche hybride + reranking distingue déjà bien les sujets entre
    # documents (voir tests), donc ça reste fiable même avec beaucoup de
    # documents. La sélection manuelle reste possible pour restreindre.
    if not doc_ids:
        doc_ids = [d.id for d in db.list_documents()]

    if not doc_ids:
        yield ("sources", [])
        yield (
            "token",
            "Importe au moins un document dans la bibliothèque avant de poser "
            "une question.",
        )
        yield ("done", None)
        return

    search_query = await _rewrite_query(message, history)
    hits = await _hybrid_search(search_query, doc_ids)

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
                snippet=hit["text"],
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
