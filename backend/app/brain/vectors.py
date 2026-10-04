"""The handbook's vector index: LlamaIndex over a ChromaDB collection (DFD "D2 Knowledge Base").

Built from the same chunks as the keyword index, sharing chunk ids, so search results from
either side refer to the same passages and can be merged.

ChromaDB keeps the collection on disk in backend/index/chroma/. The collection uses cosine
distance, and scores are reported back as cosine similarity — the scale the "is this in the
handbook?" thresholds in retriever.py were calibrated on.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.brain.bm25 import Chunk
from app.brain.llm import get_embed_model
from app.config import get_settings


class VectorsNotReadyError(RuntimeError):
    pass


def chroma_dir():
    return get_settings().index_dir / "chroma"


def collection_name() -> str:
    # Vectors only make sense for the model that made them, so each model gets its own collection.
    settings = get_settings()
    model = "mock" if settings.llm_provider == "mock" else settings.ollama_embed_model
    return "handbook-" + re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


@lru_cache
def _client():
    options = ChromaSettings(anonymized_telemetry=False)
    if get_settings().llm_provider == "mock":
        # Tests: an in-memory ChromaDB, so they exercise the same code path without touching disk.
        return chromadb.EphemeralClient(settings=options)
    chroma_dir().mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_dir()), settings=options)


def to_cosine(score: float | None) -> float:
    """The Chroma connector reports exp(-distance); with cosine distance that is exp(cos - 1)."""
    if not score:
        return 0.0
    return 1.0 + math.log(score)


def to_node(chunk: Chunk) -> TextNode:
    return TextNode(
        id_=str(chunk.chunk_id),
        text=chunk.text,
        metadata={"label": chunk.label()},
        # The label is for citations; it would only add noise to the vector.
        excluded_embed_metadata_keys=["label"],
        excluded_llm_metadata_keys=["label"],
    )


def build(chunks: list[Chunk], fingerprint: str) -> VectorStoreIndex:
    """Replace the collection with fresh embeddings of `chunks`."""
    client = _client()
    name = collection_name()
    if name in {c.name if hasattr(c, "name") else c for c in client.list_collections()}:
        client.delete_collection(name)
    collection = client.create_collection(
        name, metadata={"hnsw:space": "cosine", "built_from": fingerprint}
    )
    storage = StorageContext.from_defaults(vector_store=ChromaVectorStore(chroma_collection=collection))
    return VectorStoreIndex(
        [to_node(chunk) for chunk in chunks],
        storage_context=storage,
        embed_model=get_embed_model(),
        show_progress=get_settings().llm_provider != "mock",
    )


def load(chunks: list[Chunk], fingerprint: str) -> VectorStoreIndex:
    if get_settings().llm_provider == "mock":
        return build(chunks, fingerprint)

    try:
        collection = _client().get_collection(collection_name())
    except Exception as exc:  # chromadb raises its own NotFound type, which moved between versions
        raise VectorsNotReadyError("The AI search index hasn't been built. Run: python ingest.py") from exc

    if (collection.metadata or {}).get("built_from") != fingerprint:
        raise VectorsNotReadyError(
            "The documents changed since the AI search index was built. Run: python ingest.py"
        )
    return VectorStoreIndex.from_vector_store(
        ChromaVectorStore(chroma_collection=collection), embed_model=get_embed_model()
    )
