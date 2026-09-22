from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Escalation
from app.db.session import get_db
from app.schemas import TrackingOut

router = APIRouter(prefix="/api", tags=["tracking"])


@router.get("/track/{reference_code}", response_model=TrackingOut)
def track(reference_code: str, db: Session = Depends(get_db)) -> TrackingOut:
    """Public lookup — students check status without an account.

    Only non-sensitive fields are returned: knowing a reference code must not expose
    the student's email address or the internal routing notes.
    """
    row = (
        db.query(Escalation)
        .filter(Escalation.reference_code == reference_code.strip().upper())
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No inquiry found with that reference code. Check the code and try again.",
        )

    return TrackingOut(
        reference_code=row.reference_code,
        question=row.question,
        status=row.status,
        department=row.department.name if row.department else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        resolution_note=row.resolution_note,
    )
