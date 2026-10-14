"""The admin dashboard: inquiry trends from the query log, office workload, account roles,
and the handbook documents (DFD process 4.0, document audit)."""

from functools import lru_cache

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app import documents

from app.auth.store import User
from app.brain.memory import Memory
from app.config import get_settings
from app.routers.auth import _user_out, get_store, require_role
from app.routers.tickets import get_tickets
from app.schemas import RoleUpdate, UserOut
from app.tickets.offices import get_office, load_offices

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


@lru_cache
def get_query_log() -> Memory:
    # Its own connection to the brain's database, so reports work before the index is loaded.
    return Memory(get_settings().memory_db)


@router.get("/report")
def report(days: int = Query(default=14, ge=1, le=90)) -> dict:
    counts = get_tickets().counts_by_office()
    offices = [
        {"id": office.id, "name": office.name, **counts.get(office.id, {"open": 0, "answered": 0})}
        for office in load_offices()
    ]
    users = get_store().all()
    return {
        "inquiries": get_query_log().inquiry_report(days),
        "offices": offices,
        "accounts": {role: sum(u.role == role for u in users) for role in ("student", "department", "admin")},
    }


@router.get("/users", response_model=list[UserOut])
def users() -> list[UserOut]:
    return [_user_out(user) for user in get_store().all()]


@router.put("/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: int, body: RoleUpdate, admin: User = Depends(require_role("admin"))) -> UserOut:
    store = get_store()
    user = store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="No such account.")
    # Otherwise the last admin could lock everyone out of this page.
    if user.id == admin.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="You can't remove your own admin role.")
    office_id = body.office_id if body.role == "department" else None
    if body.role == "department" and (not office_id or get_office(office_id) is None):
        raise HTTPException(status_code=400, detail="Choose the office this staff member belongs to.")
    return _user_out(store.set_role(user.email, body.role, office_id))


# ---------- documents (DFD 4.0) ----------


@router.get("/documents")
def list_documents() -> dict:
    return {
        **documents.list_documents(),
        "rebuild": documents.rebuild_state(),
        "events": documents.get_audit_log().recent(),
    }


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...), admin: User = Depends(require_role("admin"))
) -> dict:
    # Read one byte past the limit, so an oversized file is refused without holding all of it.
    data = await file.read(documents.MAX_UPLOAD_BYTES + 1)
    try:
        replaced = documents.save_document(file.filename or "", data, admin.email)
    except documents.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"name": file.filename, "replaced": replaced}


@router.delete("/documents/{name}", status_code=204)
def delete_document(name: str, admin: User = Depends(require_role("admin"))) -> None:
    try:
        documents.delete_document(name, admin.email)
    except documents.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/rebuild", status_code=202)
def rebuild(admin: User = Depends(require_role("admin"))) -> dict:
    try:
        return documents.start_rebuild(admin.email)
    except documents.DocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
