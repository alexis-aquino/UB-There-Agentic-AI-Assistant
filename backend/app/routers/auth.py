from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.schemas import (
    GoogleSignIn,
    GuestSignIn,
    StudentLogin,
    StudentRegister,
    UserTokenResponse,
)
from app.services import user_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(user: User) -> UserTokenResponse:
    return UserTokenResponse(
        access_token=user_auth.create_user_token(user),
        email=user.email,
        full_name=user.full_name,
        account_type=user.account_type,
        auth_provider=user.auth_provider,
    )


@router.get("/config")
def auth_config() -> dict:
    """Lets the frontend show the right options without hardcoding them."""
    settings = get_settings()
    return {
        "student_email_domain": settings.student_email_domain,
        "google_enabled": bool(settings.google_client_id),
        "google_client_id": settings.google_client_id,
    }


@router.post("/guest", response_model=UserTokenResponse)
def guest(payload: GuestSignIn, db: Session = Depends(get_db)) -> UserTokenResponse:
    user = user_auth.guest_sign_in(db, payload.full_name, payload.email)
    return _token_response(user)


@router.post("/student/register", response_model=UserTokenResponse)
def student_register(payload: StudentRegister, db: Session = Depends(get_db)) -> UserTokenResponse:
    user = user_auth.student_register(
        db, payload.full_name, payload.email, payload.password, payload.student_number
    )
    return _token_response(user)


@router.post("/student/login", response_model=UserTokenResponse)
def student_login(payload: StudentLogin, db: Session = Depends(get_db)) -> UserTokenResponse:
    user = user_auth.student_login(db, payload.email, payload.password)
    return _token_response(user)


@router.post("/student/google", response_model=UserTokenResponse)
def student_google(payload: GoogleSignIn, db: Session = Depends(get_db)) -> UserTokenResponse:
    user = user_auth.google_sign_in(db, payload.id_token)
    return _token_response(user)


@router.get("/me", response_model=UserTokenResponse)
def me(user: User = Depends(user_auth.require_user)) -> UserTokenResponse:
    return _token_response(user)
