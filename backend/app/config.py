from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent

Provider = Literal["ollama", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # "ollama" runs locally and is free; "openai" calls the paid API.
    llm_provider: Provider = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embed_model: str = "text-embedding-3-small"

    chroma_dir: Path = BACKEND_ROOT / "chroma_db"
    chroma_collection: str = "university_docs"

    # A PDF page holds several unrelated topics, so indexing whole pages buries the
    # answer. Split smaller than a page, with overlap so facts aren't cut in half.
    chunk_size: int = 400
    chunk_overlap: int = 80
    retrieval_top_k: int = 5
    docs_dir: Path = PROJECT_ROOT / "upload uni info here"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def collection_name(self) -> str:
        # Providers produce different embedding dimensions, so each gets its own
        # collection — switching providers then needs a re-ingest, not a wipe.
        return f"{self.chroma_collection}_{self.llm_provider}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
