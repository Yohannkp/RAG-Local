from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.schemas import LocalIndexRequest, LocalSearchRequest, LocalSearchResult
from app.services.local_search import (
    ensure_index,
    get_index_progress,
    get_index_stats,
    index_local_files,
    search_local_files,
)

router = APIRouter(prefix="/api/local", tags=["local-search"])


@router.get("/config")
def local_config() -> dict[str, str | list[str]]:
    return {"default_root": settings.local_index_root, "ignored_dirs": settings.local_index_ignored_dirs}


@router.post("/index")
async def index_local(req: LocalIndexRequest) -> dict[str, object]:
    try:
        items = await index_local_files(req.root_path, max_files=req.max_files)
    except Exception as exc:  # pragma: no cover - garde-fou
        raise HTTPException(status_code=500, detail=f"Échec de l'indexation: {exc}") from exc
    return {"indexed": len(items), "root": req.root_path}


@router.get("/index/progress")
def index_progress() -> dict[str, object]:
    return get_index_progress()


@router.post("/search", response_model=list[LocalSearchResult])
async def search_local(req: LocalSearchRequest) -> list[LocalSearchResult]:
    try:
        results = await search_local_files(
            req.query,
            limit=req.limit,
            root_path=req.root_path,
            directory=req.directory,
            extensions=req.extensions,
            modified_after=req.modified_after,
            modified_before=req.modified_before,
        )
    except Exception as exc:  # pragma: no cover - garde-fou
        raise HTTPException(status_code=500, detail=f"Échec de la recherche: {exc}") from exc
    return [LocalSearchResult(**r) for r in results]


@router.get("/stats")
async def local_stats() -> dict[str, object]:
    """Couverture réelle de l'index (images/documents analysés, en attente, ignorés)."""
    return await get_index_stats()


@router.post("/scan")
async def local_scan() -> dict[str, object]:
    """Démarre l'indexation en arrière-plan sans attendre la fin."""
    return await ensure_index(wait=False)
