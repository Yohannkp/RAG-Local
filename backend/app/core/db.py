import uuid
from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import settings

engine = create_engine(f"sqlite:///{settings.sqlite_path}")


class Document(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    filename: str
    file_type: str
    stored_filename: str = ""
    num_chunks: int = 0
    warning: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def add_document(doc: Document) -> Document:
    with Session(engine) as session:
        session.add(doc)
        session.commit()
        session.refresh(doc)
        return doc


def update_document(doc: Document) -> Document:
    with Session(engine) as session:
        merged = session.merge(doc)
        session.commit()
        session.refresh(merged)
        return merged


def list_documents() -> list[Document]:
    with Session(engine) as session:
        return list(session.exec(select(Document).order_by(Document.created_at)))


def get_document(doc_id: str) -> Document | None:
    with Session(engine) as session:
        return session.get(Document, doc_id)


def delete_document(doc_id: str) -> None:
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        if doc:
            session.delete(doc)
            session.commit()
