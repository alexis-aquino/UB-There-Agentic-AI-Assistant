"""Rebuilds the vector index, shared by ingest.py and the admin dashboard.

Extracted so the CLI and the dashboard cannot drift apart — both must produce exactly
the same index.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import chromadb
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Document
from app.services import rag_engine
from app.services.providers import check_ready


class NoDocumentsError(RuntimeError):
    pass


def rebuild_index(db: Session | None = None, progress=print) -> dict:
    settings = get_settings()
    check_ready()

    if not settings.docs_dir.exists():
        raise NoDocumentsError(f"Folder not found: {settings.docs_dir}")

    # README.md is instructions for whoever drops files in, not university content.
    documents = SimpleDirectoryReader(str(settings.docs_dir), exclude=["README.md"]).load_data()
    if not documents:
        raise NoDocumentsError(
            f"No readable documents in {settings.docs_dir}. Add university documents first."
        )

    files = sorted({doc.metadata.get("file_name", "?") for doc in documents})
    progress(f"Loaded {len(documents)} page(s) from {len(files)} file(s)")

    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    collection = client.get_or_create_collection(settings.collection_name)

    # Re-ingesting into a populated collection would duplicate nodes, so start clean.
    existing_ids = collection.get(include=[])["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)
        progress(f"Cleared {len(existing_ids)} existing chunk(s).")

    progress(f"Embedding with {settings.llm_provider}… this can take a minute on first run.")
    rag_engine.configure_llama_index()
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    chunk_count = collection.count()

    # The cached retriever points at the old index; drop it so the next question
    # searches what was just built.
    rag_engine._retriever = None

    if db is not None:
        _sync_document_rows(db, chunk_count)

    progress(f"Indexed {chunk_count} chunk(s) into '{settings.collection_name}'.")
    return {
        "indexed": True,
        "files": files,
        "pages": len(documents),
        "chunks": chunk_count,
        "collection": settings.collection_name,
    }


def _sync_document_rows(db: Session, chunk_count: int) -> None:
    """Make the documents table reflect what is actually on disk."""
    settings = get_settings()
    now = datetime.now(timezone.utc)

    on_disk = {
        path.name: path
        for path in settings.docs_dir.iterdir()
        if path.is_file() and path.name != "README.md"
    }

    for name, path in on_disk.items():
        row = db.query(Document).filter(Document.filename == name).first()
        if row is None:
            row = Document(filename=name, uploaded_by="filesystem")
            db.add(row)
        data = path.read_bytes()
        row.size_bytes = len(data)
        row.checksum = hashlib.sha256(data).hexdigest()[:32]
        row.indexed_at = now
        # Chroma counts chunks per collection, not per file; share the total so the
        # dashboard shows something meaningful without re-deriving per-file counts.
        row.chunk_count = chunk_count if len(on_disk) == 1 else 0

    for row in db.query(Document).all():
        if row.filename not in on_disk:
            db.delete(row)

    db.commit()
