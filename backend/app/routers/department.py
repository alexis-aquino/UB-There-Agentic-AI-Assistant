"""The department dashboard's trends: the handbook questions about the staff member's own
office (matched by the office's keywords), and how that office's tickets stand."""

from fastapi import APIRouter, Depends, Query

from app.auth.store import User
from app.routers.admin import get_query_log
from app.routers.auth import require_role
from app.routers.tickets import get_tickets
from app.tickets.offices import load_offices, match_office

router = APIRouter(prefix="/api/department", tags=["department"])


@router.get("/report")
def report(
    days: int = Query(default=14, ge=1, le=90), user: User = Depends(require_role("department"))
) -> dict:
    offices = load_offices()
    return {
        "inquiries": get_query_log().inquiry_report(
            days, include=lambda question: match_office(question, offices) == user.office_id
        ),
        "tickets": get_tickets().counts_by_office().get(user.office_id, {"open": 0, "answered": 0}),
    }
