"""Model wiring for the two supported providers.

Switch with LLM_PROVIDER in backend/.env:
  ollama -> free, runs locally, no API key
  openai -> paid API, needs OPENAI_API_KEY
"""

from app.config import get_settings


class ProviderNotReadyError(RuntimeError):
    """The selected provider is missing a key or is not running."""


def check_ready() -> None:
    settings = get_settings()

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ProviderNotReadyError(
                "LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set in backend/.env. "
                "Add your key, or set LLM_PROVIDER=ollama to run the free local model."
            )
        return

    import httpx

    try:
        httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0).raise_for_status()
    except Exception as exc:
        raise ProviderNotReadyError(
            f"Cannot reach Ollama at {settings.ollama_base_url}. Start it with 'ollama serve', "
            f"or set LLM_PROVIDER=openai in backend/.env to use the OpenAI API instead."
        ) from exc


def build_chat_model():
    """The chat model the LangChain agent reasons with."""
    settings = get_settings()
    check_ready()

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.ollama_model,
        temperature=0,
        base_url=settings.ollama_base_url,
    )


def build_llama_index_models():
    """The (llm, embed_model) pair LlamaIndex uses for indexing and retrieval."""
    settings = get_settings()

    if settings.llm_provider == "openai":
        from llama_index.embeddings.openai import OpenAIEmbedding
        from llama_index.llms.openai import OpenAI

        return (
            OpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0),
            OpenAIEmbedding(model=settings.openai_embed_model, api_key=settings.openai_api_key),
        )

    from llama_index.embeddings.ollama import OllamaEmbedding
    from llama_index.llms.ollama import Ollama

    return (
        Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            request_timeout=120.0,
            # Without this it defaults to 0.75 and invents policy details.
            temperature=0,
        ),
        OllamaEmbedding(
            model_name=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        ),
    )
