import chromadb
from langchain_core.tools import Tool
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.settings import Settings as LlamaSettings
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import get_settings
from app.services.providers import build_llama_index_models

TOOL_DESCRIPTION = (
    "Searches the university's official documents — handbooks, academic policies, grading schemes, "
    "enrollment deadlines, tuition and refund rules — and returns the matching passages verbatim, "
    "each labelled with its source file and page. Input should be a natural-language question."
)

_retriever = None


def get_chroma_collection():
    settings = get_settings()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(settings.collection_name)


def get_storage_context() -> StorageContext:
    vector_store = ChromaVectorStore(chroma_collection=get_chroma_collection())
    return StorageContext.from_defaults(vector_store=vector_store)


def configure_llama_index() -> None:
    settings = get_settings()
    LlamaSettings.llm, LlamaSettings.embed_model = build_llama_index_models()
    LlamaSettings.chunk_size = settings.chunk_size
    LlamaSettings.chunk_overlap = settings.chunk_overlap


def get_retriever():
    global _retriever
    if _retriever is None:
        settings = get_settings()
        configure_llama_index()
        storage_context = get_storage_context()
        index = VectorStoreIndex.from_vector_store(
            vector_store=storage_context.vector_store,
            storage_context=storage_context,
        )
        _retriever = index.as_retriever(similarity_top_k=settings.retrieval_top_k)
    return _retriever


def query_handbooks(question: str) -> str:
    """Return the source passages themselves.

    Letting the agent read the real wording is both faster and safer than having a
    second model paraphrase it first — one less generative step to invent details.
    """
    nodes = get_retriever().retrieve(question)
    if not nodes:
        return "No matching university documents were found for that question."

    passages = []
    for node in nodes:
        name = node.metadata.get("file_name", "document")
        page = node.metadata.get("page_label")
        label = f"{name} p.{page}" if page else name
        text = " ".join(node.text.split())
        passages.append(f"[{label}]\n{text}")

    return "\n\n".join(passages)


def build_rag_tool() -> Tool:
    return Tool(
        name="University_Handbook_Retriever",
        func=query_handbooks,
        description=TOOL_DESCRIPTION,
    )
