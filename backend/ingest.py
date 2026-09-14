"""Build the ChromaDB vector index from the documents in data/sample_docs.

Run this once before starting the API, and again whenever the documents change:
    python ingest.py
"""

import sys

import chromadb
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import get_settings
from app.services.rag_engine import configure_llama_index


def main() -> int:
    settings = get_settings()

    if not settings.openai_api_key:
        print("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
        return 1

    if not settings.docs_dir.exists() or not any(settings.docs_dir.iterdir()):
        print(f"No documents found in {settings.docs_dir}. Add PDFs or text files there first.")
        return 1

    configure_llama_index()
    documents = SimpleDirectoryReader(str(settings.docs_dir)).load_data()
    print(f"Loaded {len(documents)} document(s) from {settings.docs_dir}")

    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    collection = client.get_or_create_collection(settings.chroma_collection)

    # Re-ingesting into a populated collection would duplicate nodes, so start clean.
    existing_ids = collection.get(include=[])["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)
        print(f"Cleared {len(existing_ids)} existing chunk(s).")

    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    print(f"Indexed {collection.count()} chunk(s) into '{settings.chroma_collection}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
