r"""Build the knowledge base from the documents in 'upload uni info here'.

Two indexes over the same passages: a keyword index (exact handbook terms) and a LlamaIndex
vector index stored in ChromaDB (meaning, embedded by nomic-embed-text in Ollama). Ollama must
be running.

Run after adding or changing documents:
    .\.venv\Scripts\python.exe ingest.py
"""

import sys
import time

from app.brain import vectors
from app.brain.bm25 import BM25Index
from app.brain.chunker import chunk_pages
from app.brain.engine import fingerprint_of, index_path
from app.brain.llm import ModelUnavailableError, check_models
from app.brain.readers import SUPPORTED, read_folder
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

    pages = read_folder(settings.docs_dir, exclude={"README.md"})
    if not pages:
        print(
            f"No readable documents in {settings.docs_dir}.\n"
            f"Supported types: {', '.join(sorted(SUPPORTED))}"
        )
        return 1

    files = sorted({page.source for page in pages})
    print(f"Read {len(pages)} page(s) from {len(files)} file(s): {', '.join(files)}")

    chunks = chunk_pages(pages)
    index = BM25Index()
    for chunk in chunks:
        index.add(chunk)
    index.finalize()

    path = index_path()
    index.save(path)

    print(f"Keyword index: {len(index.chunks)} passages, {len(index.postings)} terms -> {path}")

    print(f"Embedding {len(index.chunks)} passages with {settings.ollama_embed_model}...")
    started = time.perf_counter()
    vectors.build(index.chunks, fingerprint_of(path))
    print(
        f"ChromaDB collection '{vectors.collection_name()}' -> {vectors.chroma_dir()} "
        f"({time.perf_counter() - started:.0f} s)"
    )
    print("Restart the backend to use the new knowledge base.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
