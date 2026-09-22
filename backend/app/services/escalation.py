"""Creates escalations: reference code, routing, rendered email, delivery attempt."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Escalation
from app.services import mailer, router_agent

STATUSES = ["new", "sent", "acknowledged", "resolved"]


def next_reference_code(db: Session) -> str:
    """Sequential per year, e.g. UBT-2026-0001."""
    year = datetime.now(timezone.utc).year
    prefix = f"UBT-{year}-"
    count = (
        db.query(func.count(Escalation.id))
        .filter(Escalation.reference_code.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:04d}"


def create(
    db: Session,
    question: str,
    partial_answer: str,
    confidence: float,
    student_email: str = "",
    student_name: str = "",
) -> Escalation:
    decision = router_agent.route(db, question)

    escalation = Escalation(
        reference_code=next_reference_code(db),
        question=question,
        partial_answer=partial_answer,
        confidence=confidence,
        student_email=student_email,
        student_name=student_name,
        department_id=decision.department.id if decision.department else None,
        routing_reason=decision.reason,
        status="new",
    )
    db.add(escalation)
    db.flush()  # assign the id before rendering

    if decision.department:
        escalation.rendered_email = mailer.render(
            escalation, decision.department.name, decision.department.email
        )
        result = mailer.deliver(escalation, decision.department.email)
        escalation.delivery_mode = result.mode
        escalation.delivered = result.delivered
        escalation.delivery_error = result.error
        if result.delivered:
            escalation.status = "sent"

    db.commit()
    db.refresh(escalation)
    return escalation
