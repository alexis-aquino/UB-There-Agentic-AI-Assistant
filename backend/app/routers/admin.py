"""The admin dashboard's data: every question students asked, and where each one stands.

Only administrators (ADMIN_EMAILS in backend/.env, UB addresses only) can read it.
"""

import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth.store import User
from app.brain.memory import get_memory
from app.brain.topics import ALL_TOPICS
from app.routers.auth import admin_user, get_store
from app.routers.tickets import get_tickets
from app.schemas import FlagRequest
from app.tickets.store import Ticket

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _status(row: sqlite3.Row, ticket: Ticket | None) -> str:
    """answered (by the chatbot) | rerouted (it couldn't) -> pending (sent to an office) -> resolved."""
    if ticket:
        return "resolved" if ticket.status == "answered" else "pending"
    return "answered" if row["answered"] else "rerouted"


def _record(row: sqlite3.Row, ticket: Ticket | None, students: dict[int, User | None]) -> dict:
    """One inquiry, in the shape the dashboard reads (frontend/src/admin/report.js)."""
    student = students.get(row["user_id"]) if row["user_id"] is not None else None
    return {
        "id": row["id"],
        "question": row["question"],
        "topic": row["topic"],
        "student": {"name": student.name, "email": student.email} if student else None,
        "source": row["source"],
        "confidence": row["confidence"],
        "status": _status(row, ticket),
        "askedAt": row["asked_at"],
        "repliedAt": row["replied_at"],
        "escalatedAt": ticket.created_at if ticket else None,
        "resolvedAt": ticket.answered_at if ticket else None,
        "ticket": (
            {
                "ref": ticket.ref,
                "officeName": ticket.office_name,
                "answer": ticket.answer,
                "answeredBy": ticket.answered_by,
            }
            if ticket
            else None
        ),
        "flag": {"by": row["flagged_by"], "at": row["flagged_at"]} if row["flagged_by"] else None,
    }


def _students(rows: list[sqlite3.Row]) -> dict[int, User | None]:
    ids = {row["user_id"] for row in rows if row["user_id"] is not None}
    return {user_id: get_store().get(user_id) for user_id in ids}


@router.get("/inquiries")
def inquiries(_: User = Depends(admin_user)) -> dict:
    rows = get_memory().inquiries()
    tickets = get_tickets().by_inquiry()
    students = _students(rows)
    return {
        "topics": ALL_TOPICS,
        "inquiries": [_record(row, tickets.get(row["id"]), students) for row in rows],
    }


@router.put("/inquiries/{inquiry_id}/flag")
def flag(inquiry_id: int, body: FlagRequest, admin: User = Depends(admin_user)) -> dict:
    """Mark a question offensive or off-topic (or clear the mark). Flagged ones stay out of the top questions."""
    memory = get_memory()
    if memory.inquiry(inquiry_id) is None:
        raise HTTPException(status_code=404, detail="That question isn't in the log.")
    if body.flagged:
        at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        memory.flag_inquiry(inquiry_id, admin.name, at)
    else:
        memory.flag_inquiry(inquiry_id, None, None)
    row = memory.inquiry(inquiry_id)
    return _record(row, get_tickets().by_inquiry().get(inquiry_id), _students([row]))
