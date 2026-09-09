from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    chat_model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text"
    vision_model: str = "qwen3-vl:4b"
    num_ctx: int = 8192

    chunk_size_chars: int = 2400
    chunk_overlap_chars: int = 300
    top_k: int = 5

    data_dir: Path = DATA_DIR
    uploads_dir: Path = DATA_DIR / "uploads"
    chroma_dir: Path = DATA_DIR / "chroma"
    sqlite_path: Path = DATA_DIR / "registry.db"

    model_config = SettingsConfigDict(env_prefix="RAG_")


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.chroma_dir.mkdir(parents=True, exist_ok=True)
