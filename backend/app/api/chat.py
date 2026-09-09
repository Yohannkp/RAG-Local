import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest
from app.services import retrieval_service

router = APIRouter(prefix="/api", tags=["chat"])


async def _event_stream(req: ChatRequest) -> AsyncIterator[dict]:
    async for kind, payload in retrieval_service.stream_answer(
        req.message, req.doc_ids, req.history
    ):
        if kind == "sources":
            data = json.dumps([s.model_dump() for s in payload])
            yield {"event": "sources", "data": data}
        elif kind == "token":
            yield {"event": "token", "data": json.dumps({"text": payload})}
        elif kind == "done":
            yield {"event": "done", "data": "{}"}


@router.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    return EventSourceResponse(_event_stream(req))
