import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Admin, Department, Document, Escalation, Inquiry
from app.db.session import get_db
from app.schemas import (
    DepartmentOut,
    DepartmentUpdate,
    DocumentOut,
    EscalationOut,
    EscalationUpdate,
    InquiryOut,
    LoginRequest,
    TokenResponse,
)
from app.services.auth import (
    SUPERADMIN,
    create_access_token,
    current_admin,
    require_superadmin,
    verify_password,
)
from app.services.escalation import STATUSES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".csv", ".pptx"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    admin = db.query(Admin).filter(Admin.username == payload.username).first()
    if admin is None or not admin.is_active or not verify_password(
        payload.password, admin.password_hash
    ):
        # Same message either way, so the form cannot be used to discover usernames.
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    admin.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(
        access_token=create_access_token(admin),
        username=admin.username,
        role=admin.role,
        department=admin.department.name if admin.department else None,
    )


@router.get("/me")
def me(admin: Admin = Depends(current_admin)) -> dict:
    return {
        "username": admin.username,
        "role": admin.role,
        "department": admin.department.name if admin.department else None,
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db), admin: Admin = Depends(current_admin)) -> dict:
    settings = get_settings()
    escalation_q = _scoped_escalations(db, admin)

    return {
        "inquiries": db.query(func.count(Inquiry.id)).scalar() or 0,
        "escalations": escalation_q.count(),
        "open_escalations": escalation_q.filter(Escalation.status.in_(["new", "sent"])).count(),
        "documents": db.query(func.count(Document.id)).scalar() or 0,
        "mail_mode": settings.mail_mode,
        "confidence_threshold": settings.confidence_threshold,
        "provider": settings.llm_provider,
    }


# --- inquiries ---


@router.get("/inquiries", response_model=list[InquiryOut])
def list_inquiries(
    limit: int = 100,
    only_escalated: bool = False,
    db: Session = Depends(get_db),
    admin: Admin = Depends(current_admin),
) -> list[Inquiry]:
    query = db.query(Inquiry)
    if only_escalated:
        query = query.filter(Inquiry.escalated.is_(True))
    return query.order_by(Inquiry.id.desc()).limit(min(limit, 500)).all()


# --- escalations ---


def _scoped_escalations(db: Session, admin: Admin):
    """Department admins see only their own department's escalations."""
    query = db.query(Escalation)
    if admin.role != SUPERADMIN:
        query = query.filter(Escalation.department_id == admin.department_id)
    return query


@router.get("/escalations", response_model=list[EscalationOut])
def list_escalations(
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: Admin = Depends(current_admin),
) -> list[EscalationOut]:
    query = _scoped_escalations(db, admin)
    if status:
        query = query.filter(Escalation.status == status)

    rows = query.order_by(Escalation.id.desc()).limit(min(limit, 500)).all()
    return [
        EscalationOut(
            **{c.name: getattr(row, c.name) for c in Escalation.__table__.columns},
            department_name=row.department.name if row.department else None,
        )
        for row in rows
    ]


@router.patch("/escalations/{escalation_id}", response_model=EscalationOut)
def update_escalation(
    escalation_id: int,
    payload: EscalationUpdate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(current_admin),
) -> EscalationOut:
    row = _scoped_escalations(db, admin).filter(Escalation.id == escalation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Escalation not found.")

    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(
                status_code=400, detail=f"Status must be one of: {', '.join(STATUSES)}"
            )
        row.status = payload.status
    if payload.resolution_note is not None:
        row.resolution_note = payload.resolution_note

    db.commit()
    db.refresh(row)
    return EscalationOut(
        **{c.name: getattr(row, c.name) for c in Escalation.__table__.columns},
        department_name=row.department.name if row.department else None,
    )


# --- departments ---


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db), admin: Admin = Depends(current_admin)
) -> list[Department]:
    return db.query(Department).order_by(Department.name).all()


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_superadmin),
) -> Department:
    row = db.get(Department, department_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Department not found.")
    if payload.email is not None:
        row.email = str(payload.email)
    if payload.keywords is not None:
        row.keywords = payload.keywords
    db.commit()
    db.refresh(row)
    return row


# --- knowledge base ---


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db), admin: Admin = Depends(current_admin)
) -> list[Document]:
    return db.query(Document).order_by(Document.filename).all()


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_superadmin),
) -> Document:
    settings = get_settings()

    name = (file.filename or "").strip()
    suffix = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_SUFFIXES))}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds the 50 MB limit.")

    # Strip any path components so an upload cannot escape the documents folder.
    safe_name = name.replace("\\", "/").rsplit("/", 1)[-1]
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    target = settings.docs_dir / safe_name
    target.write_bytes(data)

    row = db.query(Document).filter(Document.filename == safe_name).first()
    if row is None:
        row = Document(filename=safe_name)
        db.add(row)
    row.size_bytes = len(data)
    row.checksum = hashlib.sha256(data).hexdigest()[:32]
    row.uploaded_by = admin.username
    row.indexed_at = None
    db.commit()
    db.refresh(row)
    return row


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_superadmin),
) -> dict:
    settings = get_settings()
    row = db.get(Document, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    path = settings.docs_dir / row.filename
    if path.exists():
        path.unlink()
    db.delete(row)
    db.commit()
    return {"deleted": True, "filename": row.filename, "note": "Re-index to apply the change."}


@router.post("/reindex")
def reindex(
    db: Session = Depends(get_db), admin: Admin = Depends(require_superadmin)
) -> dict:
    """Rebuild the vector index from the documents folder."""
    from app.services.indexer import rebuild_index

    try:
        result = rebuild_index(db)
    except Exception as exc:
        logger.exception("Re-index failed")
        raise HTTPException(status_code=500, detail=f"Re-index failed: {exc}") from exc
    return result
