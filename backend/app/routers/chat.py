import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Inquiry, User
from app.db.session import get_db
from app.schemas import ChatQuery, ChatResponse
from app.services import escalation as escalation_service
from app.services.agent import ask
from app.services.confidence import score_answer
from app.services.providers import ProviderNotReadyError
from app.services.rag_engine import retrieve_scored
from app.services.user_auth import optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    query: ChatQuery,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
) -> ChatResponse:
    settings = get_settings()

    try:
        reply = ask(query.message)
    except ProviderNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent invocation failed")
        raise HTTPException(
            status_code=502,
            detail=f"The assistant could not complete that request: {exc}",
        ) from exc

    verdict = score_answer(
        reply,
        retrieve_scored(query.message),
        settings.confidence_threshold,
        settings.confidence_floor_score,
        settings.confidence_ceiling_score,
    )

    reference_code = None
    department_name = None

    if verdict.escalate:
        record = escalation_service.create(
            db,
            question=query.message,
            partial_answer=reply,
            confidence=verdict.score,
            # A signed-in identity is trustworthy; the request body is not.
            student_email=user.email if user else query.student_email,
            student_name=user.full_name if user else query.student_name,
        )
        reference_code = record.reference_code
        department_name = record.department.name if record.department else None

        where = f" to the {department_name}" if department_name else ""
        reply = (
            f"{reply}\n\n"
            f"I've referred this{where} for you. Your reference code is "
            f"{reference_code} — you can use it to check the status of your inquiry."
        )

    db.add(
        Inquiry(
            session_id=(user.email if user else query.session_id),
            question=query.message,
            answer=reply,
            confidence=verdict.score,
            sources=", ".join(verdict.sources),
            escalated=verdict.escalate,
        )
    )
    db.commit()

    return ChatResponse(
        reply=reply,
        sources=verdict.sources,
        confidence=verdict.score,
        escalated=verdict.escalate,
        reference_code=reference_code,
        department=department_name,
    )
