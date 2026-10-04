import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.brain import engine
from app.brain.engine import BrainNotReadyError, ModelUnavailableError
from app.brain.llm import check_models
from app.schemas import ChatQuery, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


def _ready() -> None:
    """Raise a clean 503 before streaming starts, rather than an error mid-reply."""
    try:
        engine.load()
        check_models()
    except (BrainNotReadyError, ModelUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
def chat(query: ChatQuery) -> ChatResponse:
    _ready()
    try:
        result = engine.answer(query.message, query.session_id)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Brain failed")
        raise HTTPException(status_code=500, detail=f"The assistant hit an error: {exc}") from exc

    return ChatResponse(
        reply=result.reply,
        sources=result.sources,
        confidence=result.confidence,
        intent=result.intent,
        trace=result.trace,
        can_reroute=result.can_reroute,
        citations=result.citations,
    )


@router.post("/chat/stream")
def chat_stream(query: ChatQuery) -> StreamingResponse:
    """The reply as newline-delimited JSON: {"type":"delta","text":...} events, then "done"."""
    _ready()

    def events() -> Iterator[str]:
        try:
            for event in engine.stream_answer(query.message, query.session_id):
                yield json.dumps(event) + "\n"
        except ModelUnavailableError as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
        except Exception as exc:
            logger.exception("Brain failed mid-reply")
            yield json.dumps({"type": "error", "detail": f"The assistant hit an error: {exc}"}) + "\n"

    # X-Accel-Buffering: proxies must pass each line on as it arrives, not batch them.
    return StreamingResponse(
        events(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )
