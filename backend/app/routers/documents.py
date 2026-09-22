import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.models import Audit
from app.db.session import get_db
from app.schemas import AuditFinding, AuditResponse
from app.db.models import User
from app.services.auditor import audit
from app.services.user_auth import require_student

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["documents"])

MAX_IMAGE_BYTES = 15 * 1024 * 1024


@router.post("/audit-document", response_model=AuditResponse)
async def audit_document(
    file: UploadFile = File(...),
    form_type: str = Form("generic"),
    session_id: str = Form("default"),
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> AuditResponse:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Upload a photo or scan (JPG or PNG) of the document.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds the 15 MB limit.")

    try:
        result = audit(data, form_type)
    except Exception as exc:
        logger.exception("Document audit failed")
        raise HTTPException(status_code=500, detail=f"Could not audit the image: {exc}") from exc

    db.add(
        Audit(
            filename=file.filename or "",
            session_id=student.email or session_id,
            form_type=form_type,
            passed=result.passed,
            sharpness=result.sharpness,
            findings="; ".join(
                f"{f.check}={'ok' if f.passed else 'fail'}" for f in result.findings
            ),
            extracted_text=result.extracted_text[:4000],
        )
    )
    db.commit()

    return AuditResponse(
        filename=file.filename or "",
        passed=result.passed,
        form_type=form_type,
        sharpness=round(result.sharpness, 1),
        width=result.width,
        height=result.height,
        findings=[AuditFinding(**vars(f)) for f in result.findings],
        extracted_text=result.extracted_text,
        ocr_available=result.ocr_available,
    )
