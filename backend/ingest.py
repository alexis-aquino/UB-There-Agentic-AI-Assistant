r"""Build the knowledge base from the documents in 'upload uni info here'.

Two indexes over the same passages: a keyword index (exact handbook terms) and a LlamaIndex
vector index stored in ChromaDB (meaning, embedded by nomic-embed-text in Ollama). Ollama must
be running.

Run after adding or changing documents:
    .\.venv\Scripts\python.exe ingest.py

Admins can also do this from the admin dashboard (Documents > Rebuild), without a restart.
"""

import sys
import time

from app.brain import vectors
from app.brain.build import BuildError, build
from app.brain.llm import ModelUnavailableError, check_models
from app.config import get_settings


def main() -> int:
    settings = get_settings()

    try:
        check_models()
    except ModelUnavailableError as exc:
        print(exc)
        return 1

    if not settings.docs_dir.exists():
        print(f"Folder not found: {settings.docs_dir}")
        return 1

    started = time.perf_counter()
    try:
        build()
    except BuildError as exc:
        print(exc)
        return 1
    print(
        f"ChromaDB collection '{vectors.collection_name()}' -> {vectors.chroma_dir()} "
        f"({time.perf_counter() - started:.0f} s)"
    )
    print("Restart the backend to use the new knowledge base.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
