"""The reply-model switch: LLM_PROVIDER=ollama (default) or openai, without touching search."""

import pytest

from app.brain import llm
from app.config import get_settings


@pytest.fixture
def provider(monkeypatch):
    """Switch the provider for one test; the cached model objects are rebuilt around it."""

    def use(name, **settings):
        monkeypatch.setattr(get_settings(), "llm_provider", name)
        for key, value in settings.items():
            monkeypatch.setattr(get_settings(), key, value)
        llm.get_llm.cache_clear()
        llm.get_embed_model.cache_clear()

    yield use
    llm.get_llm.cache_clear()
    llm.get_embed_model.cache_clear()


def test_openai_writes_replies_but_search_stays_on_ollama(provider):
    provider("openai", openai_api_key="sk-test", openai_model="gpt-4o-mini")
    from llama_index.embeddings.ollama import OllamaEmbedding
    from llama_index.llms.openai import OpenAI

    model = llm.get_llm()
    assert isinstance(model, OpenAI) and model.model == "gpt-4o-mini"
    # The ChromaDB index and its calibrated thresholds belong to nomic-embed-text.
    assert isinstance(llm.get_embed_model(), OllamaEmbedding)
    assert llm.reply_model_name() == "gpt-4o-mini (OpenAI)"


def test_openai_without_a_key_says_so_clearly(provider):
    provider("openai", openai_api_key="")
    with pytest.raises(llm.ModelUnavailableError, match="OPENAI_API_KEY"):
        llm.check_models()


def test_ollama_is_the_default():
    assert type(get_settings()).model_fields["llm_provider"].default == "ollama"
