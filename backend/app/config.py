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

    # --- database ---
    # SQLite by default so the app runs with no install. Point this at
    # postgresql+psycopg://user:pass@host/db for deployment — no code changes needed.
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'ubthere.db').as_posix()}"

    # --- admin auth ---
    jwt_secret: str = "change-me-in-env-before-deploying"
    jwt_expire_minutes: int = 480
    seed_admin_username: str = "admin"
    seed_admin_password: str = ""  # blank generates a random one, printed once at startup

    # --- student / guest accounts ---
    # UB mail is Google Workspace, so this is both the password-signup domain and the
    # hosted-domain (hd) claim checked on Google ID tokens.
    student_email_domain: str = "ub.edu.ph"
    # Leave blank to disable Sign in with Google; set it to the OAuth client ID to enable.
    google_client_id: str = ""

    # --- escalation ---
    confidence_threshold: float = 0.45
    # Similarity band used to normalise retrieval scores. Embedding-model specific;
    # measured for nomic-embed-text against the UB handbook.
    confidence_floor_score: float = 0.35
    confidence_ceiling_score: float = 0.65
    # "dry_run" records escalations without sending. NEVER default to live: real
    # university inboxes must not receive test traffic.
    mail_mode: Literal["dry_run", "live"] = "dry_run"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "ubthere-noreply@ub.edu.ph"
    smtp_use_tls: bool = True

    # --- voice (optional peripheral for the avatar) ---
    voice_provider: Literal["piper", "xtts", "off"] = "piper"
    voice_language: str = "en"
    piper_voice: str = "en_US-lessac-medium"
    piper_dir: Path = BACKEND_ROOT / "voice_models"
    voice_cache_dir: Path = BACKEND_ROOT / "voice_cache"
    voice_sample_path: Path = BACKEND_ROOT / "voice_models" / "my_voice.wav"

    # --- document auditing ---
    tesseract_cmd: str = ""  # set if tesseract.exe is not on PATH
    min_sharpness: float = 100.0
    min_width: int = 800

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
