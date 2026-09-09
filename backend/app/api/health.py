from fastapi import APIRouter

from app.core.ollama_client import ollama_client
from app.models.schemas import HealthOut

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    reachable = await ollama_client.is_reachable()
    models = await ollama_client.has_required_models() if reachable else {}
    return HealthOut(ollama_reachable=reachable, models=models)
