import asyncio
import logging
from pathlib import Path

from app.core import db, vector_store
from app.core.ollama_client import ollama_client
from app.core.parsing.docx_parser import parse_docx
from app.core.parsing.pdf_parser import parse_pdf
from app.core.parsing.txt_parser import parse_txt
from app.services.chunking import chunk_units

logger = logging.getLogger(__name__)


async def _describe_images(images: list[bytes]) -> list[str]:
    """Decrit chaque image via le modele de vision locale (OCR + comprehension
    du contenu). Une image dont l'analyse echoue est ignoree plutot que de
    faire echouer tout l'import du document."""
    if not images:
        return []

    async def _safe_describe(img: bytes) -> str | None:
        try:
            return await ollama_client.describe_image(img)
        except Exception:
            logger.exception("Echec de l'analyse d'image par le modele de vision")
            return None

    results = await asyncio.gather(*(_safe_describe(img) for img in images))
    return [r for r in results if r]


def _append_image_descriptions(text: str, descriptions: list[str]) -> str:
    if not descriptions:
        return text
    blocks = "\n\n".join(f"[Image] {d}" for d in descriptions)
    return f"{text}\n\n{blocks}" if text else blocks


def _build_pdf_warning(
    empty_pages: list[int], images_analyzed: int, total_pages: int
) -> str | None:
    if empty_pages:
        is_plural = len(empty_pages) > 1
        pages_str = ", ".join(str(p) for p in empty_pages)
        if len(empty_pages) == total_pages:
            return (
                "Ce PDF semble entièrement scanné ou vide (aucun texte ni image "
                "analysable) — ce document ne sera pas cherchable."
            )
        return (
            f"{'Les pages' if is_plural else 'La page'} {pages_str} "
            f"{'sont' if is_plural else 'est'} vide{'s' if is_plural else ''} ou "
            f"sans contenu analysable — {'leur' if is_plural else 'son'} contenu "
            "ne sera pas cherchable. Le reste du document est indexé normalement."
        )
    if images_analyzed:
        plural = "s" if images_analyzed > 1 else ""
        return (
            f"{images_analyzed} image{plural} analysée{plural} automatiquement par "
            "IA (OCR / description) — la transcription peut être imprécise, "
            "vérifie les passages importants."
        )
    return None


def _build_docx_warning(images_analyzed: int) -> str | None:
    if not images_analyzed:
        return None
    plural = "s" if images_analyzed > 1 else ""
    return (
        f"{images_analyzed} image{plural} analysée{plural} automatiquement par "
        "IA (OCR / description) — la transcription peut être imprécise, "
        "vérifie les passages importants."
    )


async def ingest_file(path: Path, filename: str, file_type: str) -> db.Document:
    warning: str | None = None

    if file_type == "pdf":
        pages = parse_pdf(str(path))
        empty_pages: list[int] = []
        images_analyzed = 0
        units = []
        for p in pages:
            descriptions = await _describe_images(p.images)
            images_analyzed += len(descriptions)
            text = _append_image_descriptions(p.text, descriptions)
            if len(text) < 20:
                empty_pages.append(p.page_number)
            units.append((text, {"page_number": p.page_number}))
        warning = _build_pdf_warning(empty_pages, images_analyzed, len(pages))
    elif file_type == "docx":
        sections = parse_docx(str(path))
        images_analyzed = 0
        units = []
        for s in sections:
            descriptions = await _describe_images(s.images)
            images_analyzed += len(descriptions)
            text = _append_image_descriptions(s.text, descriptions)
            units.append((text, {"section_title": s.section_title}))
        warning = _build_docx_warning(images_analyzed)
    elif file_type == "txt":
        units = [(parse_txt(str(path)), {})]
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    doc = db.add_document(
        db.Document(filename=filename, file_type=file_type, warning=warning)
    )

    chunks = chunk_units(units)
    if chunks:
        texts = [c.text for c in chunks]
        embeddings = await ollama_client.embed(texts)
        metadatas = [
            {
                **c.metadata,
                "doc_id": doc.id,
                "filename": filename,
                "file_type": file_type,
            }
            for c in chunks
        ]
        vector_store.add_chunks(doc.id, texts, embeddings, metadatas)

    doc.num_chunks = len(chunks)
    doc = db.update_document(doc)
    return doc


def delete_document(doc_id: str) -> None:
    vector_store.delete_by_doc_id(doc_id)
    db.delete_document(doc_id)
