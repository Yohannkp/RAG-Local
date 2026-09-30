import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import LocalChatRequest
from app.services import local_chat

router = APIRouter(prefix="/api/local", tags=["local-chat"])


async def _event_stream(req: LocalChatRequest) -> AsyncIterator[dict]:
    async for kind, payload in local_chat.stream_local_answer(
        req.query,
        req.history,
        limit=req.limit,
        root_path=req.root_path,
        directory=req.directory,
        extensions=req.extensions,
        modified_after=req.modified_after,
        modified_before=req.modified_before,
    ):
        if kind == "sources":
            yield {"event": "sources", "data": json.dumps(payload)}
        elif kind == "token":
            yield {"event": "token", "data": json.dumps({"text": payload})}
        elif kind == "done":
            yield {"event": "done", "data": "{}"}


@router.post("/chat")
async def chat_local(req: LocalChatRequest) -> EventSourceResponse:
    return EventSourceResponse(_event_stream(req))