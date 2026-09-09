from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size_chars,
    chunk_overlap=settings.chunk_overlap_chars,
    separators=["\n\n", "\n", ". ", " ", ""],
)


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_units(units: list[tuple[str, dict[str, Any]]]) -> list[Chunk]:
    """Split each (text, metadata) unit independently so chunks never cross a
    page (PDF) or section (DOCX) boundary — this keeps citation metadata accurate.
    """
    chunks: list[Chunk] = []
    for text, unit_metadata in units:
        if not text or not text.strip():
            continue
        pieces = _splitter.split_text(text)
        for i, piece in enumerate(pieces):
            start = text.find(piece)
            metadata = {
                **unit_metadata,
                "chunk_index": i,
                "char_start": start if start >= 0 else None,
                "char_end": (start + len(piece)) if start >= 0 else None,
            }
            chunks.append(Chunk(text=piece, metadata=metadata))
    return chunks
