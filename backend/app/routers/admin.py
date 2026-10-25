"""The admin dashboard's data: every question students asked and where each one stands, and
every account, with disabling and deleting.

Only administrators (ADMIN_EMAILS in backend/.env, UB addresses only) can read it.
"""

import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth.store import User
from app.brain.memory import get_memory
from app.brain.topics import ALL_TOPICS
from app.config import get_settings
from app.routers.auth import _in_domain, admin_user, get_store, is_admin
from app.routers.tickets import get_tickets
from app.schemas import AccountsRequest, FlagRequest
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
    if student:
        asker = {"name": student.name, "email": student.email}
    elif row["asker_name"]:
        asker = {"name": row["asker_name"], "email": row["asker_email"], "deleted": True}
    else:
        asker = None  # asked without signing in
    return {
        "id": row["id"],
        "question": row["question"],
        "topic": row["topic"],
        "student": asker,
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


# ---------- accounts ----------


def _utc(timestamp: str | None) -> str | None:
    # users.created_at is SQLite's CURRENT_TIMESTAMP: UTC without a zone.
    if not timestamp:
        return None
    return timestamp if timestamp.endswith("Z") else f"{timestamp.replace(' ', 'T')}Z"


def _days_since(iso: str) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 86400


def _accounts() -> dict:
    """Every account, in the shape the Accounts page reads (frontend/src/admin/accounts.js)."""
    activity = get_memory().activity_by_user()
    accounts = []
    for row in get_store().all_rows():
        questions, last_asked = activity.get(row["id"], (0, None))
        last_active = max(filter(None, [_utc(row["last_active_at"]), last_asked]), default=None)
        user = User(row["id"], row["email"], row["name"], None, bool(row["google_linked"]), False)
        accounts.append(
            {
                "id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "role": "admin" if is_admin(user) else "student" if _in_domain(row["email"]) else "guest",
                "signIn": "UB mail" if row["google_linked"] else "Email & password",
                "createdAt": _utc(row["created_at"]),
                "lastActiveAt": last_active,
                "questions": questions,
                "disabled": {"by": row["disabled_by"], "at": row["disabled_at"]} if row["disabled_by"] else None,
            }
        )
    accounts.sort(key=lambda a: a["lastActiveAt"] or "", reverse=True)
    return {"accounts": accounts, "deleteAfterDays": get_settings().account_delete_after_days}


def _others(ids: list[int], admin: User) -> list[int]:
    """Administrators can't disable or delete their own account, so they can't lock themselves out."""
    return [i for i in dict.fromkeys(ids) if i != admin.id]


@router.get("/accounts")
def accounts(_: User = Depends(admin_user)) -> dict:
    return _accounts()


@router.post("/accounts/disable")
def disable_accounts(body: AccountsRequest, admin: User = Depends(admin_user)) -> dict:
    """Disabled accounts can't sign in, and are signed out where they already are."""
    get_store().set_disabled(_others(body.ids, admin), admin.name)
    return _accounts()


@router.post("/accounts/enable")
def enable_accounts(body: AccountsRequest, admin: User = Depends(admin_user)) -> dict:
    get_store().set_disabled(_others(body.ids, admin), None)
    return _accounts()


@router.post("/accounts/delete")
def delete_accounts(body: AccountsRequest, admin: User = Depends(admin_user)) -> dict:
    """Deletes accounts that have been disabled for account_delete_after_days. Their office
    questions go too; their chat questions stay in the report, still under their name."""
    wait = get_settings().account_delete_after_days
    rows = {row["id"]: row for row in get_store().all_rows()}
    ready = [
        i
        for i in _others(body.ids, admin)
        if i in rows and rows[i]["disabled_at"] and _days_since(rows[i]["disabled_at"]) >= wait
    ]
    if len(ready) < len(set(body.ids)):
        raise HTTPException(
            status_code=400,
            detail=f"Only accounts disabled for at least {wait} days can be deleted, and not your own.",
        )
    get_tickets().delete_for_users(ready)
    get_memory().keep_asker({i: (rows[i]["name"], rows[i]["email"]) for i in ready})
    get_store().delete(ready)
    return _accounts()
