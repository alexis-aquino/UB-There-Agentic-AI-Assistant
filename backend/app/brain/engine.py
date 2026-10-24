"""The brain: turns a student's message into a conversational reply.

Flow: detect small talk -> hybrid search (LlamaIndex vectors + handbook keywords) -> llama3.2
writes the reply from those excerpts, streamed word by word -> log the turn.

Replies stream so the screen and the voice can start before the model finishes.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core.llms import ChatMessage, MessageRole

from app.brain import vectors
from app.brain.bm25 import BM25Index
from app.brain.intents import QUESTION, detect_intent
from app.brain.llm import ModelUnavailableError, check_models, get_embed_model, get_llm, reply_model_name
from app.brain.memory import Memory, get_memory
from app.brain.prompts import build_messages
from app.brain.retriever import HybridRetriever
from app.brain.topics import topic_of
from app.brain.text import split_sentences
from app.config import get_settings
from app.sources import parse_label

logger = logging.getLogger(__name__)

__all__ = ["BrainNotReadyError", "ModelUnavailableError", "Reply", "answer", "stream_answer"]


class BrainNotReadyError(RuntimeError):
    """The indexes have not been built yet."""


@dataclass
class Reply:
    reply: str
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    intent: str = QUESTION
    trace: list[str] = field(default_factory=list)
    can_reroute: bool = False
    inquiry_id: int | None = None
    citations: list[dict] = field(default_factory=list)


@dataclass
class Brain:
    keywords: BM25Index
    vectors: VectorStoreIndex
    memory: Memory
    fingerprint: str


_brain: Brain | None = None
_load_lock = threading.Lock()

# Recent turns per conversation, so follow-ups ("what about seniors?") make sense.
_sessions: OrderedDict[str, deque[ChatMessage]] = OrderedDict()
_sessions_lock = threading.Lock()
MAX_SESSIONS = 500

# A short or pronoun-led message continues the previous question, so search with both.
FOLLOW_UP_RE = re.compile(
    r"^\s*(and|but|so|also|then|what about|how about|what if|why|is that|does that|"
    r"it|its|it's|that|this|they|those|them)\b",
    re.I,
)
# The model is told to say exactly this when the excerpts don't answer the question.
NOT_FOUND_RE = re.compile(
    r"couldn[’']?t find|could not find|can[’']?t find|not (?:mentioned|covered) in|"
    r"(?:doesn[’']?t|does not) (?:say|mention|cover)",
    re.I,
)


def index_path() -> Path:
    return get_settings().index_dir / "bm25_index.json"


def fingerprint_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def load() -> Brain:
    global _brain
    with _load_lock:
        if _brain is None:
            path = index_path()
            if not path.exists():
                raise BrainNotReadyError(
                    "No index found. Put documents in 'upload uni info here' and run "
                    "'python ingest.py' to build the knowledge base."
                )
            keywords = BM25Index.load(path)
            fingerprint = fingerprint_of(path)
            try:
                vector_index = vectors.load(keywords.chunks, fingerprint)
            except vectors.VectorsNotReadyError as exc:
                raise BrainNotReadyError(str(exc)) from exc
            _brain = Brain(keywords, vector_index, get_memory(), fingerprint)
        return _brain


def reset() -> None:
    """Drop loaded state so the next call reloads — used after re-ingesting."""
    global _brain
    with _load_lock:
        _brain = None
    with _sessions_lock:
        _sessions.clear()


def warmup() -> None:
    """Load indexes and wake the models, so the first real question isn't the slow one."""
    try:
        load()
        check_models()
        get_embed_model().get_query_embedding("warm up")
        # Wake the local model; an API model needs no warming, and each call would cost money.
        if get_settings().llm_provider == "ollama":
            get_llm().complete("Reply with one word: ready")
        logger.info("Brain warmed up")
    except Exception as exc:  # warm-up is best effort; questions report errors properly
        logger.warning("Brain warm-up skipped: %s", exc)


def _history(session_id: str) -> deque[ChatMessage]:
    with _sessions_lock:
        turns = _sessions.get(session_id)
        if turns is None:
            turns = deque(maxlen=get_settings().memory_turns * 2)
            _sessions[session_id] = turns
            while len(_sessions) > MAX_SESSIONS:
                _sessions.popitem(last=False)
        else:
            _sessions.move_to_end(session_id)
        return turns


def _search_query(message: str, history: deque[ChatMessage]) -> tuple[str, bool]:
    previous = next((m.content for m in reversed(history) if m.role == MessageRole.USER), None)
    if previous and (len(message.split()) <= 6 or FOLLOW_UP_RE.match(message)):
        return f"{previous} {message}", True
    return message, False


def _explain_model_error(exc: Exception) -> str:
    """Plain words for the errors a student or admin can act on."""
    kind = type(exc).__name__
    if kind == "AuthenticationError":
        return "OpenAI rejected the API key in backend/.env. Check OPENAI_API_KEY and restart the backend."
    if kind == "RateLimitError":
        return "OpenAI is refusing requests: the account is out of credit or over its rate limit."
    if kind in {"APIConnectionError", "APITimeoutError", "ConnectError", "ReadTimeout"}:
        return "Couldn't reach the AI model. Check the internet connection (OpenAI) or that Ollama is running."
    if kind == "NotFoundError":
        return "The AI model name wasn't found. Check OPENAI_MODEL / OLLAMA_MODEL in backend/.env."
    return f"The AI model hit an error: {exc}"


def _citations(nodes: list, key_sentences: str, limit: int = 3) -> list[dict]:
    """Where the answer came from: page, file and the passage to highlight, best first.

    The passage holding the exact answering sentence (when the keyword search found one)
    leads; otherwise each excerpt is quoted by its opening sentences.
    """
    key = " ".join(key_sentences.split())
    citations: list[dict] = []
    for node in nodes:
        label = node.node.metadata.get("label")
        if not label or any(c["label"] == label for c in citations):
            continue
        text = " ".join(node.node.get_content().split())
        holds_key = bool(key) and key[:60] in text
        quote = key if holds_key else " ".join(split_sentences(text)[:2])[:400]
        file, page = parse_label(label)
        citation = {
            "label": label,
            "file": file,
            "page": page,
            "quote": quote,
            # A picture of the page can be shown for PDFs.
            "image": page is not None and file.lower().endswith(".pdf"),
        }
        if holds_key:
            citations.insert(0, citation)
        else:
            citations.append(citation)
    return citations[:limit]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stream_answer(message: str, session_id: str = "default", user_id: int | None = None) -> Iterator[dict]:
    """Yields {"type": "delta", "text"} events as the reply is written, then one "done" event.

    `user_id` is the signed-in student, if any; it goes into the inquiry log for the admin report.
    """
    brain = load()
    check_models()
    started = time.perf_counter()
    asked_at = _now()
    settings = get_settings()

    brain.memory.log_turn(session_id, "student", message)
    history = _history(session_id)
    intent = detect_intent(message)
    trace: list[str] = []
    nodes = []
    confidence = 0.0
    key_sentences = ""

    if intent == QUESTION:
        query, follow_up = _search_query(message, history)
        if follow_up:
            trace.append("Follow-up: searched together with your previous question.")
        retriever = HybridRetriever(brain.keywords, brain.vectors, top_k=settings.context_passages)
        nodes = retriever.retrieve(query)
        trace.extend(retriever.report.trace)
        confidence = retriever.report.confidence if nodes else 0.0
        key_sentences = retriever.report.key_sentences
    else:
        trace.append(f"Handled as {intent} — no handbook search needed.")

    messages = build_messages(
        message, nodes, list(history), small_talk=intent != QUESTION, key_sentences=key_sentences
    )

    text = ""
    try:
        for chunk in get_llm().stream_chat(messages):
            if chunk.delta:
                text += chunk.delta
                yield {"type": "delta", "text": chunk.delta}
    except ModelUnavailableError:
        raise
    except Exception as exc:
        raise ModelUnavailableError(_explain_model_error(exc)) from exc
    # Small models sometimes wrap the whole reply in quotes, echoing how the task quoted
    # the student's message.
    text = text.strip().strip('"“”').strip()
    if not text:
        raise ModelUnavailableError("The AI model returned an empty reply. Please try again.")

    said_not_found = bool(NOT_FOUND_RE.search(text))
    citations = [] if said_not_found else _citations(nodes, key_sentences)
    sources = [c["label"] for c in citations]

    history.append(ChatMessage(role=MessageRole.USER, content=message))
    history.append(ChatMessage(role=MessageRole.ASSISTANT, content=text))
    brain.memory.log_turn(session_id, "assistant", text)

    trace.append(f"Written by {reply_model_name()} in {time.perf_counter() - started:.1f} s.")

    can_reroute = intent == QUESTION and (not nodes or said_not_found)
    confidence = round(confidence if sources else 0.0, 2)
    # Small talk isn't an inquiry; every handbook question is, answered or not.
    inquiry_id = None
    if intent == QUESTION:
        inquiry_id = brain.memory.log_inquiry(
            session_id,
            user_id,
            message,
            topic_of(message),
            answered=not can_reroute,
            source=sources[0] if sources else None,
            confidence=confidence,
            asked_at=asked_at,
            replied_at=_now(),
        )

    yield {
        "type": "done",
        "reply": text,
        "sources": sources,
        "citations": citations,
        "confidence": confidence,
        "intent": intent,
        "trace": trace,
        # Offer "Ask an office" whenever the handbook didn't answer it.
        "can_reroute": can_reroute,
        "inquiry_id": inquiry_id,
    }


def answer(message: str, session_id: str = "default", user_id: int | None = None) -> Reply:
    """The whole reply at once, for callers that don't stream."""
    for event in stream_answer(message, session_id, user_id):
        if event["type"] == "done":
            return Reply(
                reply=event["reply"],
                sources=event["sources"],
                confidence=event["confidence"],
                intent=event["intent"],
                trace=event["trace"],
                can_reroute=event["can_reroute"],
                citations=event["citations"],
                inquiry_id=event["inquiry_id"],
            )
    raise ModelUnavailableError("The AI model stopped before finishing its reply.")


def status() -> dict:
    settings = get_settings()
    try:
        brain = load()
    except BrainNotReadyError as exc:
        return {"ready": False, "detail": str(exc)}

    model_ok = True
    detail = "ready"
    try:
        check_models()
    except ModelUnavailableError as exc:
        model_ok, detail = False, str(exc)

    return {
        "ready": model_ok,
        "detail": detail,
        "chunks": len(brain.keywords.chunks),
        "provider": settings.llm_provider,
        "model": reply_model_name(),
        "embed_model": "mock" if settings.llm_provider == "mock" else settings.ollama_embed_model,
        "fingerprint": brain.fingerprint,
        **brain.memory.stats(),
    }
