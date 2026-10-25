import logging
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse

from app import mail
from app.auth.store import User
from app.brain.memory import get_memory
from app.config import get_settings
from app.routers.auth import current_user, get_store
from app.schemas import OfficeList, TicketCreate, TicketOut
from app.tickets.offices import get_office, load_offices, suggest_office
from app.tickets.pages import answer_page, closed_page, not_found_page
from app.tickets.store import Ticket, TicketStore

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

    # Linked only to the student's own question, so nobody can attach a ticket to someone else's.
    inquiry = get_memory().inquiry(body.inquiry_id) if body.inquiry_id else None
    inquiry_id = inquiry["id"] if inquiry and inquiry["user_id"] == user.id else None

    ticket, token = store.create(user.id, office.id, office.name, body.question, inquiry_id)
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
    if student is None:  # account deleted
        return HTMLResponse(closed_page(ticket), status_code=410)
    return HTMLResponse(answer_page(ticket, student.name, t))


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
    if student is None:  # account deleted: the answer would reach nobody
        return HTMLResponse(closed_page(ticket), status_code=410)
    student_name = student.name

    answer = answer.strip()[:5000]
    if not answer:
        return HTMLResponse(
            answer_page(ticket, student_name, t, error="Please write an answer first."), status_code=400
        )
    ticket = store.answer(ticket.id, answer, answered_by.strip()[:80])

    # Email only verified addresses (Google sign-in): a guest's address was never checked,
    # so the app must not send mail to it. Guests see the answer in the app.
    if student and student.google_linked:
        try:
            mail.send(student.email, *_student_email(ticket))
        except mail.MailError:
            logger.warning("Could not email %s about %s; the answer is still in the app.", student.id, ticket.ref)

    return HTMLResponse(answer_page(ticket, student_name, t, saved=True))
