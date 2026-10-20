"""The department dashboard's reports and content (DFD process 6.0), for the staff member's own
office: the inquiry trends and student query logs about that office (matched by the office's
keywords), and the knowledge-base files the office uploaded ("Department Information")."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app import documents
from app.auth.store import User
from app.routers.admin import get_query_log, named
from app.routers.auth import require_role
from app.routers.tickets import get_tickets
from app.tickets.offices import load_offices, match_office

router = APIRouter(prefix="/api/department", tags=["department"])


def _about_office(user: User):
    """Whether a question (or document type) is about the staff member's office."""
    offices = load_offices()
    return lambda text: match_office(text, offices) == user.office_id


@router.get("/report")
def report(
    days: int = Query(default=14, ge=1, le=90), user: User = Depends(require_role("department"))
) -> dict:
    return {
        "inquiries": get_query_log().inquiry_report(days, include=_about_office(user)),
        "tickets": get_tickets().counts_by_office().get(user.office_id, {"open": 0, "answered": 0}),
    }


@router.get("/logs")
def logs(
    days: int = Query(default=14, ge=1, le=90),
    q: str = Query(default="", max_length=100),
    user: User = Depends(require_role("department")),
) -> dict:
    return {"entries": named(get_query_log().query_log(days, q, include=_about_office(user)))}


# ---------- the office's own files ----------


@router.get("/documents")
def list_documents(user: User = Depends(require_role("department"))) -> dict:
    listing = documents.list_documents(office_id=user.office_id)
    return {
        **listing,
        "rebuild": documents.rebuild_state(),
        "events": documents.get_audit_log().recent(files={d["name"] for d in listing["documents"]}),
    }


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...), user: User = Depends(require_role("department"))
) -> dict:
    data = await file.read(documents.MAX_UPLOAD_BYTES + 1)
    try:
        replaced = documents.save_document(file.filename or "", data, user.email, office_id=user.office_id)
    except documents.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"name": file.filename, "replaced": replaced}


@router.delete("/documents/{name}", status_code=204)
def delete_document(name: str, user: User = Depends(require_role("department"))) -> None:
    try:
        documents.delete_document(name, user.email, office_id=user.office_id)
    except documents.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/rebuild", status_code=202)
def rebuild(user: User = Depends(require_role("department"))) -> dict:
    # The index is shared, so this rebuilds every office's files; the change log says who asked.
    try:
        return documents.start_rebuild(user.email)
    except documents.DocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
