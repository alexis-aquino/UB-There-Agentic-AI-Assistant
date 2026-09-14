import logging

from fastapi import APIRouter, HTTPException

from app.schemas import ChatQuery, ChatResponse
from app.services.agent import MissingAPIKeyError, ask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(query: ChatQuery) -> ChatResponse:
    try:
        reply = ask(query.message)
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent invocation failed")
        raise HTTPException(
            status_code=502,
            detail=f"The assistant could not complete that request: {exc}",
        ) from exc
    return ChatResponse(reply=reply)
