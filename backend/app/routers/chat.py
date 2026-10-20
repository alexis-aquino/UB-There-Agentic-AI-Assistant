import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app import doccheck, documents
from app.auth.store import User
from app.brain import engine
from app.brain.engine import BrainNotReadyError, ModelUnavailableError
from app.brain.llm import check_models
from app.routers.auth import current_user
from app.schemas import ChatQuery, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


def _ready() -> None:
    """Raise a clean 503 before streaming starts, rather than an error mid-reply."""
    # The indexes are being replaced; searching them half-built would give wrong answers.
    if documents.is_rebuilding():
        raise HTTPException(
            status_code=503, detail="The handbook is being updated. Please ask again in a minute."
        )
    try:
        engine.load()
        check_models()
    except (BrainNotReadyError, ModelUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _session(query: ChatQuery, user: User) -> str:
    """Conversations belong to an account: another user can't continue one by guessing its id."""
    return f"{user.id}:{query.session_id}"


@router.post("/chat", response_model=ChatResponse)
def chat(query: ChatQuery, user: User = Depends(current_user)) -> ChatResponse:
    _ready()
    try:
        result = engine.answer(query.message, _session(query, user))
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
def chat_stream(query: ChatQuery, user: User = Depends(current_user)) -> StreamingResponse:
    """The reply as newline-delimited JSON: {"type":"delta","text":...} events, then "done"."""
    _ready()
    session_id = _session(query, user)

    def events() -> Iterator[str]:
        try:
            for event in engine.stream_answer(query.message, session_id):
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


@router.post("/documents/check")
async def check_document(
    file: UploadFile = File(...), note: str = Form(""), user: User = Depends(current_user)
) -> dict:
    """A photo of a document, checked against the handbook's rules for it. Nothing is stored."""
    _ready()
    # One byte past the limit, so an oversized photo is refused without reading all of it.
    image = await file.read(doccheck.MAX_IMAGE_BYTES + 1)
    try:
        return doccheck.check(image, user.id, note)
    except doccheck.CheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
