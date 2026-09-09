import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.core import db
from app.models.schemas import DocumentOut
from app.services import ingestion_service

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}

router = APIRouter(prefix="/api/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}


@router.get("", response_model=list[DocumentOut])
def list_documents() -> list[DocumentOut]:
    return [DocumentOut(**d.model_dump()) for d in db.list_documents()]


@router.post("", response_model=DocumentOut)
async def upload_document(file: UploadFile) -> DocumentOut:
    suffix = Path(file.filename or "").suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(suffix)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté: {suffix or 'inconnu'}. "
            "Formats acceptés: PDF, DOCX, TXT.",
        )

    dest_path = settings.uploads_dir / f"{uuid.uuid4().hex}{suffix}"
    content = await file.read()
    dest_path.write_bytes(content)

    try:
        doc = await ingestion_service.ingest_file(
            dest_path, file.filename or dest_path.name, file_type
        )
    except Exception as exc:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Échec du traitement: {exc}") from exc

    return DocumentOut(**doc.model_dump())


@router.get("/{doc_id}/file")
def get_document_file(doc_id: str) -> FileResponse:
    doc = db.get_document(doc_id)
    if not doc or not doc.stored_filename:
        raise HTTPException(status_code=404, detail="Document introuvable")
    file_path = settings.uploads_dir / doc.stored_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le disque")
    return FileResponse(
        file_path,
        media_type=MEDIA_TYPES.get(doc.file_type, "application/octet-stream"),
        filename=doc.filename,
    )


@router.delete("/{doc_id}")
def delete_document(doc_id: str) -> dict[str, bool]:
    if not db.get_document(doc_id):
        raise HTTPException(status_code=404, detail="Document introuvable")
    ingestion_service.delete_document(doc_id)
    return {"deleted": True}
