"""Build the ChromaDB vector index from the documents in the upload folder.

Run this once before starting the API, and again whenever the documents change:
    .\\.venv\\Scripts\\python.exe ingest.py
"""

import sys

import chromadb
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import get_settings
from app.services.providers import ProviderNotReadyError, check_ready
from app.services.rag_engine import configure_llama_index


def main() -> int:
    settings = get_settings()

    try:
        check_ready()
    except ProviderNotReadyError as exc:
        print(exc)
        return 1

    if not settings.docs_dir.exists() or not any(settings.docs_dir.iterdir()):
        print(f"No documents found in {settings.docs_dir}. Add PDFs or text files there first.")
        return 1

    configure_llama_index()
    # README.md is instructions for whoever drops files in, not university content.
    documents = SimpleDirectoryReader(str(settings.docs_dir), exclude=["README.md"]).load_data()
    if not documents:
        print(f"Only the README is in {settings.docs_dir}. Add university documents there first.")
        return 1
    print(f"Loaded {len(documents)} document(s) from {settings.docs_dir}")

    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    collection = client.get_or_create_collection(settings.collection_name)

    # Re-ingesting into a populated collection would duplicate nodes, so start clean.
    existing_ids = collection.get(include=[])["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)
        print(f"Cleared {len(existing_ids)} existing chunk(s).")

    print(f"Embedding with {settings.llm_provider}… this can take a minute on first run.")
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    print(f"Indexed {collection.count()} chunk(s) into '{settings.collection_name}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
