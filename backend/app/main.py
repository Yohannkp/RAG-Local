import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import chat, documents, health, local_chat, local_search
from app.core.db import init_db
from app.services.local_watcher import local_file_watcher

app = FastAPI(title="RAG Local", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(health.router)
app.include_router(local_search.router)
app.include_router(local_chat.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.on_event("startup")
async def start_local_watcher() -> None:
    if settings.local_watch_enabled:
        asyncio.create_task(local_file_watcher.start())


@app.on_event("shutdown")
async def stop_local_watcher() -> None:
    await local_file_watcher.stop()
