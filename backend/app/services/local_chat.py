from collections.abc import AsyncIterator

from app.config import settings
from app.core.ollama_client import ollama_client
from app.models.schemas import ChatMessage
from app.services.local_search import (
    ensure_index,
    find_matches,
    is_locate_query,
    is_photo_query,
)

LOCAL_SYSTEM_PROMPT = """Tu es l'assistant privé de l'ordinateur de l'utilisateur.
Réponds uniquement à partir des fichiers locaux fournis dans le contexte.
- Cite les fichiers avec [1], [2], etc.
- Pour une demande de localisation, donne directement le chemin complet.
- N'invente jamais de lieu, date, personne ou contenu absent du contexte.
- Réponds dans la langue de la question.

Fichiers locaux vérifiés comme pertinents :
{context}
"""


def _context(results: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] {r['path']}\nType: {r['extension']}\nDescription/extrait:\n{r['snippet']}"
        for i, r in enumerate(results, start=1)
    )


def coverage_sentence(stats: dict) -> str:
    """Phrase honnête sur ce qui a réellement été analysé."""
    parts = [
        f"{stats['images_indexed']} image(s) sur {stats['images_total']} et "
        f"{stats['documents_indexed']} document(s) sur {stats['documents_total']} analysés"
    ]
    if stats.get("skipped_small_images"):
        parts.append(f"{stats['skipped_small_images']} petites images (icônes) ignorées")
    if stats.get("failed"):
        parts.append(f"{stats['failed']} fichier(s) illisibles")
    return ", ".join(parts)


def absence_message(stats: dict, examined: int) -> str:
    if stats["complete"]:
        return (
            "Je n'ai trouvé aucun fichier correspondant sur ton ordinateur. "
            f"L'analyse est complète ({coverage_sentence(stats)}) : "
            f"j'ai examiné les {examined} fichiers les plus proches et aucun ne correspond."
        )
    reasons = []
    if stats["running"] or stats["images_pending"] or stats["documents_pending"]:
        reasons.append(
            f"l'indexation est encore en cours ({stats['images_pending']} image(s) et "
            f"{stats['documents_pending']} document(s) restent à analyser)"
        )
    if stats["truncated"]:
        reasons.append("la limite de fichiers a été atteinte")
    if stats["failed"]:
        reasons.append(f"{stats['failed']} fichier(s) n'ont pas pu être lus")
    why = " ; ".join(reasons) or "l'analyse n'est pas terminée"
    return (
        "Je n'ai rien trouvé pour l'instant, mais je ne peux pas affirmer que ça n'existe pas : "
        f"{why}. Couverture actuelle : {coverage_sentence(stats)}. Réessaie quand l'indexation sera terminée."
    )


def list_answer(matches: list[dict], stats: dict, shown: int) -> str:
    lines = [f"J'ai trouvé {len(matches)} fichier(s) correspondant à ta demande :", ""]
    for i, m in enumerate(matches[:shown], start=1):
        desc = (m.get("description") or "").strip().replace("\n", " ")
        lines.append(f"[{i}] {m['path']}" + (f" — {desc[:140]}" if desc else ""))
    if len(matches) > shown:
        lines.append(f"… et {len(matches) - shown} autre(s) (voir la liste des sources).")
    if not stats["complete"]:
        lines += ["", f"Attention, l'analyse n'est pas terminée ({coverage_sentence(stats)}) : il peut y en avoir d'autres."]
    return "\n".join(lines)


async def stream_local_answer(
    message: str,
    history: list[ChatMessage],
    limit: int = 8,
    root_path: str | None = None,
    directory: str | None = None,
    extensions: list[str] | None = None,
    modified_after: str | None = None,
    modified_before: str | None = None,
) -> AsyncIterator[tuple[str, object]]:
    stats = await ensure_index(root_path or settings.local_index_root)
    outcome = await find_matches(message, root_path, directory, extensions, modified_after, modified_before)
    matches = outcome["matches"]
    locate = is_photo_query(message) or is_locate_query(message)
    shown = max(limit, 30) if locate else limit
    yield ("sources", matches[:shown])

    if not matches:
        yield ("token", absence_message(stats, outcome["examined"]))
        yield ("done", None)
        return
    if locate:
        yield ("token", list_answer(matches, stats, shown))
        yield ("done", None)
        return

    messages = [
        {"role": "system", "content": LOCAL_SYSTEM_PROMPT.format(context=_context(matches[:limit]))},
        *[{"role": item.role, "content": item.content} for item in history[-8:]],
        {"role": "user", "content": message},
    ]
    async for token in ollama_client.chat_stream(messages):
        yield ("token", token)
    yield ("done", None)
