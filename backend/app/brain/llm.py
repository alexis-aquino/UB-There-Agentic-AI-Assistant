"""The language model and embedding model, through LlamaIndex.

LLM_PROVIDER picks who writes the replies:
  ollama (default) — llama3.2 on this machine, free and offline
  openai           — an OpenAI model (OPENAI_MODEL) through the API; needs OPENAI_API_KEY
  mock             — a small offline stand-in so the tests run without either

Search always uses nomic-embed-text in Ollama, whichever model writes the replies: the
ChromaDB index was built with it, and the "is this in the handbook?" thresholds were
calibrated on its scores. Switching the reply model therefore needs no re-ingest.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.llms.types import (
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)
from llama_index.core.llms import LLM
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.llms.custom import CustomLLM

from app.brain.text import content_terms
from app.config import get_settings


class ModelUnavailableError(RuntimeError):
    """A model can't be reached: Ollama isn't running or lacks a model, or no OpenAI key."""


def reply_model_name() -> str:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return "offline test model"
    if settings.llm_provider == "openai":
        return f"{settings.openai_model} (OpenAI)"
    return f"{settings.ollama_model} (Ollama)"


@lru_cache
def get_llm() -> LLM:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return ExtractiveMockLLM()

    if settings.llm_provider == "openai":
        from llama_index.llms.openai import OpenAI

        return OpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=60.0,
            max_retries=2,
        )

    from llama_index.llms.ollama import Ollama

    return Ollama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
        context_window=4096,
        request_timeout=120.0,
        keep_alive="30m",  # stay loaded on the GPU between questions
        additional_kwargs={"num_predict": settings.llm_max_tokens},
    )


@lru_cache
def get_json_llm() -> LLM:
    """The same model as get_llm, set to answer in JSON with room for a longer reply: the
    document check (app/doccheck.py) asks it for a verdict per requirement."""
    settings = get_settings()
    if settings.llm_provider == "mock":
        return ExtractiveMockLLM()

    if settings.llm_provider == "openai":
        from llama_index.llms.openai import OpenAI

        return OpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
            max_tokens=900,
            timeout=60.0,
            max_retries=2,
            additional_kwargs={"response_format": {"type": "json_object"}},
        )

    from llama_index.llms.ollama import Ollama

    return Ollama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        context_window=4096,
        request_timeout=120.0,
        keep_alive="30m",
        json_mode=True,
        additional_kwargs={"num_predict": 900},
    )


@lru_cache
def get_embed_model() -> BaseEmbedding:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return HashEmbedding()

    from llama_index.embeddings.ollama import OllamaEmbedding

    return OllamaEmbedding(
        model_name=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
        keep_alive="30m",
        # nomic-embed-text is trained with these prefixes; search is noticeably worse without.
        query_instruction="search_query: ",
        text_instruction="search_document: ",
    )


def check_models() -> None:
    """Fail fast with a clear message instead of a request timing out mid-answer."""
    settings = get_settings()
    if settings.llm_provider == "mock":
        return
    if settings.llm_provider == "openai" and not settings.openai_api_key.strip():
        raise ModelUnavailableError(
            "LLM_PROVIDER=openai, but OPENAI_API_KEY is empty in backend/.env. "
            "Add the key and restart the backend."
        )
    try:
        with urllib.request.urlopen(f"{settings.ollama_base_url}/api/tags", timeout=3) as response:
            models = {m["name"].split(":")[0] for m in json.load(response).get("models", [])}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ModelUnavailableError(
            "The AI model isn't running. Start Ollama (open the Ollama app), then ask again."
        ) from exc

    # Ollama always serves search; it serves the replies too unless OpenAI does.
    needed = [settings.ollama_embed_model]
    if settings.llm_provider == "ollama":
        needed.insert(0, settings.ollama_model)
    for name in needed:
        if name.split(":")[0] not in models:
            raise ModelUnavailableError(f"Ollama is missing the model '{name}'. Run: ollama pull {name}")


# ---------------------------------------------------------------------------------------
# Offline stand-ins for tests (LLM_PROVIDER=mock)
# ---------------------------------------------------------------------------------------


class HashEmbedding(BaseEmbedding):
    """Bag-of-words vectors: similarity tracks shared handbook terms. Deterministic."""

    dims: int = 512

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dims
        for term in content_terms(text):
            slot = int(hashlib.md5(term.encode("utf-8")).hexdigest(), 16) % self.dims
            vector[slot] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._vector(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)


class ExtractiveMockLLM(CustomLLM):
    """Answers with the first sentence of the first excerpt, or says it found nothing."""

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(context_window=4096, num_output=256, model_name="mock")

    def _reply(self, prompt: str) -> str:
        if "This is small talk" in prompt:
            return "Hi! What would you like to know about the handbook?"
        if "has nothing about this" in prompt:
            return "I couldn't find that in the handbook. You can tap “Ask an office” and I'll pass it along."
        excerpts = prompt.split("Handbook excerpts:", 1)[-1].split("The student asked:", 1)[0]
        body = re.sub(r"^\[[^\]]*\]\s*", "", excerpts.strip())
        first = re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0]
        return f"Sure! Here's what the handbook says: {first.strip()}"

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        return CompletionResponse(text=self._reply(prompt))

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponseGen:
        text = ""
        for word in re.findall(r"\S+\s*", self._reply(prompt)):
            text += word
            yield CompletionResponse(text=text, delta=word)
