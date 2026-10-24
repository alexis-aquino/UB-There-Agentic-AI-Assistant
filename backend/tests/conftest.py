"""Shared fixtures.

Settings are read from the environment the first time get_settings() runs, so the test
overrides must be in place before anything under app/ is imported.
"""

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="ub_there_tests_"))
os.environ["MEMORY_DB"] = str(_TMP / "brain_memory.db")  # never touch the real memory
os.environ["TICKETS_DB"] = str(_TMP / "tickets.db")
os.environ["MAIL_OUTBOX_DIR"] = str(_TMP / "outbox")  # MAIL_MODE defaults to log: nothing is sent
os.environ["SOURCE_CACHE_DIR"] = str(_TMP / "source_cache")
os.environ["USERS_DB"] = str(_TMP / "users.db")  # never touch real accounts
os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"
# A UB admin, and a guest address that is listed but must not become an admin.
os.environ["ADMIN_EMAILS"] = "Boss@ub.edu.ph, outsider@example.com"
os.environ["LLM_PROVIDER"] = "mock"  # offline stand-in model: the tests never need Ollama
os.environ["VOICE_PROVIDER"] = "off"  # keep tests fast and independent of Piper
os.environ["VOICE_CACHE_DIR"] = str(_TMP / "voice_cache")
os.environ["VOICE_DATASET_DIR"] = str(_TMP / "voice_dataset")  # never touch real recordings
os.environ["VOICE_STUDIO_HOSTS"] = "127.0.0.1,::1,localhost,testclient"  # TestClient's host
os.environ["VOICE_PROMPTS_PATH"] = str(_TMP / "prompts.txt")
(_TMP / "prompts.txt").write_text(
    "Hello, and welcome to the University of Batangas.\n"
    "The library opens at nine in the morning.\n"
    "Please wait a moment while I search.\n",
    encoding="utf-8",
)

from app.brain import engine  # noqa: E402


@pytest.fixture(scope="session")
def index():
    """The real index built by ingest.py. Retrieval tests skip if it has not been built."""
    if not engine.index_path().exists():
        pytest.skip("No index — run 'python ingest.py' first.")
    return engine.load().keywords
