"""Building the knowledge base from the documents folder, shared by ingest.py and the admin dashboard.

Next to the indexes it writes manifest.json: each file's hash and passage count at build time,
so the dashboard can tell which documents are new, changed or gone since the last build.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.brain import vectors
from app.brain.bm25 import BM25Index
from app.brain.chunker import chunk_pages
from app.brain.engine import fingerprint_of, index_path
from app.brain.readers import SUPPORTED, read_file
from app.config import get_settings

# Notes for whoever manages the folder, never indexed.
SKIPPED = {"README.md"}


class BuildError(RuntimeError):
    pass


@dataclass
class BuildResult:
    files: list[str]
    pages: int
    passages: int
    terms: int


def manifest_path() -> Path:
    return get_settings().index_dir / "manifest.json"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def document_files(folder: Path | None = None) -> list[Path]:
    """The files a build reads: supported types, README excluded."""
    folder = folder or get_settings().docs_dir
    if not folder.exists():
        return []
    return [
        path
        for path in sorted(folder.iterdir())
        if path.is_file() and path.name not in SKIPPED and path.suffix.lower() in SUPPORTED
    ]


def read_manifest() -> dict | None:
    try:
        return json.loads(manifest_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def build(on_progress=print) -> BuildResult:
    """Read every document, rebuild both indexes and the manifest. Ollama must be running."""
    folder = get_settings().docs_dir
    files = document_files(folder)
    if not files:
        raise BuildError(f"No readable documents in {folder}. Supported types: {', '.join(sorted(SUPPORTED))}")

    pages_by_file = {path.name: read_file(path) for path in files}
    pages = [page for file_pages in pages_by_file.values() for page in file_pages]
    if not pages:
        raise BuildError("None of the documents had readable text (a scanned PDF needs OCR first).")
    on_progress(f"Read {len(pages)} page(s) from {len(files)} file(s): {', '.join(p.name for p in files)}")

    chunks = chunk_pages(pages)
    index = BM25Index()
    for chunk in chunks:
        index.add(chunk)
    index.finalize()

    path = index_path()
    index.save(path)
    on_progress(f"Keyword index: {len(index.chunks)} passages, {len(index.postings)} terms -> {path}")

    on_progress(f"Embedding {len(index.chunks)} passages...")
    vectors.build(index.chunks, fingerprint_of(path))

    passages = {}
    for chunk in index.chunks:
        passages[chunk.source] = passages.get(chunk.source, 0) + 1
    manifest = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fingerprint": fingerprint_of(path),
        "files": {
            p.name: {
                "sha256": file_hash(p),
                "size": p.stat().st_size,
                "pages": len(pages_by_file[p.name]),
                "passages": passages.get(p.name, 0),
            }
            for p in files
        },
    }
    manifest_path().write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return BuildResult(
        files=[p.name for p in files], pages=len(pages), passages=len(index.chunks), terms=len(index.postings)
    )
