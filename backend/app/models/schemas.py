from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    num_chunks: int
    warning: str | None
    created_at: datetime


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    doc_ids: list[str]
    history: list[ChatMessage] = []


class SourceOut(BaseModel):
    index: int
    doc_id: str
    filename: str
    page_number: int | None = None
    section_title: str | None = None
    snippet: str


class HealthOut(BaseModel):
    ollama_reachable: bool
    models: dict[str, bool]


class LocalIndexRequest(BaseModel):
    root_path: str
    max_files: int = 5000


class LocalSearchRequest(BaseModel):
    query: str
    limit: int = 5
    root_path: str | None = None
    directory: str | None = None
    extensions: list[str] | None = None
    modified_after: str | None = None
    modified_before: str | None = None


class LocalChatRequest(LocalSearchRequest):
    history: list[ChatMessage] = []


class LocalSearchResult(BaseModel):
    path: str
    filename: str
    directory: str
    extension: str
    snippet: str
    score: float
    modified_at: str | None = None
