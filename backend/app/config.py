from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent

VoiceProvider = Literal["piper", "xtts", "off"]
MailMode = Literal["log", "smtp"]
LlmProvider = Literal["ollama", "openai", "mock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- brain ---
    docs_dir: Path = PROJECT_ROOT / "upload uni info here"
    index_dir: Path = BACKEND_ROOT / "index"
    memory_db: Path = BACKEND_ROOT / "brain_memory.db"
    # Rendered pictures of source pages (see app/sources.py); safe to delete any time.
    source_cache_dir: Path = BACKEND_ROOT / "source_cache"

    # --- AI model (LlamaIndex) ---
    # Who writes the replies: "ollama" (local, free), "openai" (API, needs a key), or "mock"
    # (offline stand-in for the tests). Search always uses ollama_embed_model.
    llm_provider: LlmProvider = "ollama"
    openai_api_key: str = ""  # only read when llm_provider = "openai"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"  # not "localhost": on Windows that tries IPv6 first and stalls ~2 s
    ollama_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    llm_temperature: float = 0.1  # low: stick to what the excerpts say
    # Replies are read aloud, so they are kept short; this also bounds how long one takes.
    llm_max_tokens: int = 320
    # Excerpts given to the model per answer, and turns of conversation it remembers.
    context_passages: int = 3  # each one adds ~150 tokens the GPU must read before replying
    memory_turns: int = 6

    # --- voice (optional peripheral; the brain never imports these) ---
    voice_provider: VoiceProvider = "piper"
    voice_language: str = "en"
    piper_voice: str = "en_US-lessac-medium"
    piper_dir: Path = BACKEND_ROOT / "voice_models"
    voice_cache_dir: Path = BACKEND_ROOT / "voice_cache"
    voice_sample_path: Path = BACKEND_ROOT / "voice_models" / "my_voice.wav"

    # --- training your own Piper voice (see voice_training/) ---
    voice_prompts_path: Path = BACKEND_ROOT / "voice_training" / "prompts.txt"
    voice_dataset_dir: Path = BACKEND_ROOT / "voice_dataset"
    # The recording studio (http://localhost:8100/voice-studio) only answers requests from
    # these addresses, i.e. the machine running the backend. Students never see it.
    voice_studio_hosts: str = "127.0.0.1,::1,localhost"

    # --- accounts ---
    users_db: Path = BACKEND_ROOT / "users.db"
    # Every new account starts with this password (sign-up default, and Google sign-ups).
    default_password: str = "12345678"
    # From Google Cloud Console > Credentials > OAuth client ID (Web). Empty = Google sign-in off.
    google_client_id: str = ""
    # Google sign-in is only for this Workspace domain; everyone else signs up as a guest.
    google_domain: str = "ub.edu.ph"
    session_days: int = 7
    # Who can open the admin dashboard, comma-separated. Only addresses in google_domain count,
    # so with Google sign-in on, an admin is always a verified UB account.
    admin_emails: str = ""
    # An account can be deleted only after it has been disabled this long (admin Accounts page).
    account_delete_after_days: int = 30

    # --- asking an office (rerouted questions) ---
    offices_path: Path = BACKEND_ROOT / "offices.json"
    tickets_db: Path = BACKEND_ROOT / "tickets.db"
    tickets_per_day: int = 5  # per student, so offices can't be flooded
    # The address students and office staff open the app at; answer links are built from it.
    public_base_url: str = "http://localhost:5273"

    # --- outgoing email ---
    # "log" saves each email as a file in mail_outbox_dir instead of sending it.
    mail_mode: MailMode = "log"
    mail_outbox_dir: Path = BACKEND_ROOT / "outbox"
    mail_from_name: str = "UB There"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""  # the app's own address, e.g. ubthere.assistant@gmail.com
    smtp_password: str = ""  # a Google "app password", not the account password

    frontend_origins: str = "http://localhost:5273,http://127.0.0.1:5273"

    @property
    def studio_hosts(self) -> set[str]:
        return {host.strip() for host in self.voice_studio_hosts.split(",") if host.strip()}

    @property
    def admins(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails.split(",") if email.strip()}

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
