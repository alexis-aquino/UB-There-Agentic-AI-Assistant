from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.auth.store import User
from app.brain.memory import get_memory
from app.config import get_settings
from app.routers.auth import current_user, get_store, is_admin, kind_of, optional_user, staff_user
from app.schemas import AnswerRequest, OfficeList, StaffTicketOut, TicketCreate, TicketOut
from app.tickets.offices import get_office, load_recipients, suggest_office
from app.tickets.store import Ticket, TicketStore

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


def _staff_out(ticket: Ticket) -> StaffTicketOut:
    student = get_store().get(ticket.user_id)
    return StaffTicketOut(
        **_out(ticket).model_dump(),
        student_name=student.name if student else None,
        student_department=student.department if student and kind_of(student) == "student" else None,
        closed=student is None,
    )


def _inbox_of(staff: User) -> str | None:
    """The office or college whose questions a staff account answers; None for administrators (all)."""
    return None if is_admin(staff) else staff.department


@router.get("/api/offices", response_model=OfficeList)
def offices(question: str = "", user: User | None = Depends(optional_user)) -> OfficeList:
    # A signed-in student's own college is suggested when no office fits the question.
    department = user.department if user and kind_of(user) == "student" else None
    return OfficeList(
        offices=[{"id": office.id, "name": office.name, "kind": office.kind} for office in load_recipients()],
        suggested=suggest_office(question, department),
    )


@router.post("/api/tickets", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, user: User = Depends(current_user)) -> TicketOut:
    settings = get_settings()
    office = get_office(body.office_id)
    if office is None:
        raise HTTPException(status_code=400, detail="Please choose an office or department.")

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

    # It waits in the dashboard of the office or college it was sent to.
    return _out(store.create(user.id, office.id, office.name, body.question, inquiry_id))


@router.get("/api/tickets", response_model=list[TicketOut])
def my_tickets(user: User = Depends(current_user)) -> list[TicketOut]:
    return [_out(ticket) for ticket in get_tickets().for_user(user.id)]


@router.get("/api/admin/tickets", response_model=list[StaffTicketOut])
def inbox(staff: User = Depends(staff_user)) -> list[StaffTicketOut]:
    """The questions sent to this account's office or college, newest first. Administrators see
    every one, and can answer any (for an office or college with no account yet)."""
    return [_staff_out(ticket) for ticket in get_tickets().for_office(_inbox_of(staff))]


@router.post("/api/admin/tickets/{ref}/answer", response_model=StaffTicketOut)
def answer(ref: str, body: AnswerRequest, staff: User = Depends(staff_user)) -> StaffTicketOut:
    store = get_tickets()
    ticket = store.get_by_ref(ref)
    office = _inbox_of(staff)
    if ticket is None or (office and ticket.office_name != office):
        raise HTTPException(status_code=404, detail="That question wasn't sent to you.")
    if ticket.status == "answered":
        raise HTTPException(status_code=409, detail="This question has already been answered.")
    if get_store().get(ticket.user_id) is None:
        raise HTTPException(status_code=410, detail="The student's account was deleted, so the answer would reach nobody.")
    return _staff_out(store.answer(ticket.id, body.answer, staff.name))
