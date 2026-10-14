import logging
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse

from app import mail
from app.auth.store import User
from app.config import get_settings
from app.routers.auth import current_user, get_store, require_role
from app.schemas import OfficeList, StaffTicketOut, TicketAnswer, TicketCreate, TicketOut
from app.tickets.offices import get_office, load_offices, suggest_office
from app.tickets.pages import answer_page, not_found_page
from app.tickets.store import Ticket, TicketStore, parse_ref

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tickets"])


@lru_cache
def get_tickets() -> TicketStore:
    return TicketStore(get_settings().tickets_db)


def _out(ticket: Ticket) -> TicketOut:
    return TicketOut(
        ref=ticket.ref,
        office_id=ticket.office_id,
        office_name=ticket.office_name,
        question=ticket.question,
        status=ticket.status,
        answer=ticket.answer,
        answered_by=ticket.answered_by,
        created_at=ticket.created_at,
        answered_at=ticket.answered_at,
    )


def _office_email(ticket: Ticket, student: User, link: str) -> tuple[str, str]:
    subject = f"[{ticket.ref}] Student question: {ticket.question[:60]}"
    if len(ticket.question) > 60:
        subject += "…"
    body = f"""Hello {ticket.office_name},

A student asked UB There, the University of Batangas handbook assistant, a question it
could not answer from the handbook:

    {ticket.question}

Asked by: {student.name}
Reference: {ticket.ref}
Sent: {datetime.now():%d %b %Y, %I:%M %p}

Please answer here — your answer goes straight to the student in the app:
{link}

This link is private to this one question. Replies to this email are not read.

— UB There
"""
    return subject, body


def _student_email(ticket: Ticket) -> tuple[str, str]:
    base = get_settings().public_base_url.rstrip("/")
    subject = f"[{ticket.ref}] The {ticket.office_name} answered your question"
    by = ticket.answered_by or ""
    by = f" ({by})" if by and ticket.office_name.lower() not in by.lower() else ""
    body = f"""Hi,

The {ticket.office_name}{by} answered the question you asked through UB There.

Your question:
    {ticket.question}

Their answer:
    {ticket.answer}

You can also see it under "My questions" in UB There: {base}/

— UB There
"""
    return subject, body


def _save_answer(ticket: Ticket, student: User | None, answer: str, answered_by: str) -> Ticket:
    """Store the office's answer and tell the student, from the email link or the dashboard."""
    ticket = get_tickets().answer(ticket.id, answer, answered_by)
    # Email only verified addresses (Google sign-in): a guest's address was never checked,
    # so the app must not send mail to it. Guests see the answer in the app.
    if student and student.google_linked:
        try:
            mail.send(student.email, *_student_email(ticket))
        except mail.MailError:
            logger.warning("Could not email %s about %s; the answer is still in the app.", student.id, ticket.ref)
    return ticket


@router.get("/api/offices", response_model=OfficeList)
def offices(question: str = "") -> OfficeList:
    return OfficeList(
        offices=[{"id": office.id, "name": office.name} for office in load_offices()],
        suggested=suggest_office(question),
    )


@router.post("/api/tickets", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, user: User = Depends(current_user)) -> TicketOut:
    settings = get_settings()
    office = get_office(body.office_id)
    if office is None:
        raise HTTPException(status_code=400, detail="Please choose an office.")

    store = get_tickets()
    if store.count_since(user.id, hours=24) >= settings.tickets_per_day:
        raise HTTPException(
            status_code=429,
            detail=f"You can send up to {settings.tickets_per_day} questions to offices a day. "
            "Please try again tomorrow.",
        )

    ticket, token = store.create(user.id, office.id, office.name, body.question)
    link = f"{settings.public_base_url.rstrip('/')}/answer/{ticket.ref}?t={token}"
    try:
        mail.send(office.email, *_office_email(ticket, user, link))
    except mail.MailError as exc:
        # Nobody will ever answer a question the office never received.
        store.delete(ticket.id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _out(ticket)


@router.get("/api/tickets", response_model=list[TicketOut])
def my_tickets(user: User = Depends(current_user)) -> list[TicketOut]:
    return [_out(ticket) for ticket in get_tickets().for_user(user.id)]


@router.get("/answer/{ref}", response_class=HTMLResponse, include_in_schema=False)
def answer_form(ref: str, t: str = "") -> HTMLResponse:
    ticket = get_tickets().get_with_token(ref, t)
    if ticket is None:
        return HTMLResponse(not_found_page(), status_code=404)
    student = get_store().get(ticket.user_id)
    return HTMLResponse(answer_page(ticket, student.name if student else "a student", t))


@router.post("/answer/{ref}", response_class=HTMLResponse, include_in_schema=False)
def submit_answer(
    ref: str,
    t: str = Form(""),
    answer: str = Form(""),
    answered_by: str = Form(""),
) -> HTMLResponse:
    store = get_tickets()
    ticket = store.get_with_token(ref, t)
    if ticket is None:
        return HTMLResponse(not_found_page(), status_code=404)
    student = get_store().get(ticket.user_id)
    student_name = student.name if student else "a student"

    answer = answer.strip()[:5000]
    if not answer:
        return HTMLResponse(
            answer_page(ticket, student_name, t, error="Please write an answer first."), status_code=400
        )
    ticket = _save_answer(ticket, student, answer, answered_by.strip()[:80])
    return HTMLResponse(answer_page(ticket, student_name, t, saved=True))


# ---------- department dashboard: office staff answer in the app ----------


def _staff_out(ticket: Ticket) -> StaffTicketOut:
    student = get_store().get(ticket.user_id)
    return StaffTicketOut(
        **_out(ticket).model_dump(), student_name=student.name if student else "A former student"
    )


@router.get("/api/department/tickets", response_model=list[StaffTicketOut])
def office_tickets(user: User = Depends(require_role("department"))) -> list[StaffTicketOut]:
    return [_staff_out(ticket) for ticket in get_tickets().for_office(user.office_id)]


@router.post("/api/department/tickets/{ref}/answer", response_model=StaffTicketOut)
def answer_ticket(
    ref: str, body: TicketAnswer, user: User = Depends(require_role("department"))
) -> StaffTicketOut:
    ticket_id = parse_ref(ref)
    ticket = get_tickets().get(ticket_id) if ticket_id is not None else None
    # Another office's question looks the same as a missing one: staff see only their own.
    if ticket is None or ticket.office_id != user.office_id:
        raise HTTPException(status_code=404, detail="Your office has no question with that reference.")
    student = get_store().get(ticket.user_id)
    ticket = _save_answer(ticket, student, body.answer, body.answered_by.strip() or user.name)
    return _staff_out(ticket)
