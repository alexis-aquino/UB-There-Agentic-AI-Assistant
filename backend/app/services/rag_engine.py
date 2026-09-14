import chromadb
from langchain_core.tools import Tool
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.settings import Settings as LlamaSettings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import get_settings

TOOL_DESCRIPTION = (
    "Answers questions about university handbooks, academic policies, grading schemes, "
    "enrollment deadlines, tuition and refund rules, and other official regulations. "
    "Input should be a natural-language question."
)

_query_engine = None


def get_chroma_collection():
    settings = get_settings()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(settings.chroma_collection)


def get_storage_context() -> StorageContext:
    vector_store = ChromaVectorStore(chroma_collection=get_chroma_collection())
    return StorageContext.from_defaults(vector_store=vector_store)


def configure_llama_index() -> None:
    settings = get_settings()
    LlamaSettings.llm = OpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
    LlamaSettings.embed_model = OpenAIEmbedding(api_key=settings.openai_api_key)


def get_query_engine():
    global _query_engine
    if _query_engine is None:
        configure_llama_index()
        storage_context = get_storage_context()
        index = VectorStoreIndex.from_vector_store(
            vector_store=storage_context.vector_store,
            storage_context=storage_context,
        )
        _query_engine = index.as_query_engine(similarity_top_k=3)
    return _query_engine


def query_handbooks(question: str) -> str:
    return str(get_query_engine().query(question))


def build_rag_tool() -> Tool:
    return Tool(
        name="University_Handbook_Retriever",
        func=query_handbooks,
        description=TOOL_DESCRIPTION,
    )
