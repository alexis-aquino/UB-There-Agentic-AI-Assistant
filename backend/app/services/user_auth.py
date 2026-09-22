"""Authentication for students and guests.

Two audiences, matching the paper's two versions (Scope, p. 11):

* Guests are prospective students. They give a name and an email, nothing more —
  demanding a password from someone still deciding whether to apply would defeat the
  purpose.
* Current students use their UB address. That domain is Google Workspace, so Sign in
  with Google is the correct production path; password sign-up exists so the system is
  usable before OAuth credentials are issued.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.services.auth import hash_password, verify_password

GUEST = "guest"
STUDENT = "student"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Separate scheme from the admin one so a student token can never be used on admin
# routes, and auto_error=False lets chat stay usable without signing in.
bearer = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def validate_email_shape(email: str) -> str:
    email = normalise_email(email)
    if not EMAIL_RE.match(email):
        raise AuthError("That doesn't look like a valid email address.")
    return email


def is_student_domain(email: str) -> bool:
    domain = get_settings().student_email_domain.strip().lower().lstrip("@")
    if not domain:
        return True  # domain checking disabled
    return normalise_email(email).endswith("@" + domain)


def require_student_domain(email: str) -> str:
    email = validate_email_shape(email)
    if not is_student_domain(email):
        domain = get_settings().student_email_domain
        raise AuthError(
            f"Current students must sign in with their UB email address (@{domain}). "
            "If you are not yet enrolled, continue as a guest instead."
        )
    return email


def create_user_token(user: User) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "account_type": user.account_type,
        "name": user.full_name,
        "scope": "user",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


# --- guest ---


def guest_sign_in(db: Session, full_name: str, email: str) -> User:
    email = validate_email_shape(email)
    full_name = full_name.strip()
    if len(full_name) < 2:
        raise AuthError("Please enter your full name.")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, full_name=full_name, account_type=GUEST)
        db.add(user)
    elif user.account_type == STUDENT:
        raise AuthError(
            "That email is registered as a current student. Use the student sign-in instead."
        )
    else:
        user.full_name = full_name

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


# --- student, password ---


def student_register(
    db: Session, full_name: str, email: str, password: str, student_number: str = ""
) -> User:
    email = require_student_domain(email)
    if len(password) < 8:
        raise AuthError("Choose a password of at least 8 characters.")
    if len(full_name.strip()) < 2:
        raise AuthError("Please enter your full name.")

    existing = db.query(User).filter(User.email == email).first()
    if existing is not None and existing.password_hash:
        raise AuthError("An account already exists for that email. Sign in instead.")

    user = existing or User(email=email)
    user.full_name = full_name.strip()
    user.account_type = STUDENT
    user.password_hash = hash_password(password)
    user.auth_provider = "local"
    user.student_number = student_number.strip()
    user.last_login_at = datetime.now(timezone.utc)
    if existing is None:
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


def student_login(db: Session, email: str, password: str) -> User:
    email = normalise_email(email)
    user = db.query(User).filter(User.email == email).first()

    # Same message whichever half failed, so the form cannot enumerate accounts.
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise AuthError("Incorrect email or password.", status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        raise AuthError("This account has been deactivated.", status.HTTP_403_FORBIDDEN)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


# --- student, Sign in with Google ---


def google_sign_in(db: Session, id_token_str: str) -> User:
    """Verify a Google ID token and sign the student in.

    Google's own library checks the signature, issuer, audience and expiry. The hosted
    domain claim is then checked separately: without it, any personal Gmail account
    would be accepted as a UB student.
    """
    settings = get_settings()
    if not settings.google_client_id:
        raise AuthError(
            "Sign in with Google is not configured on this server.",
            status.HTTP_501_NOT_IMPLEMENTED,
        )

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:
        raise AuthError(
            "Google sign-in support is not installed. Run: pip install google-auth",
            status.HTTP_501_NOT_IMPLEMENTED,
        ) from exc

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), settings.google_client_id
        )
    except ValueError as exc:
        raise AuthError(f"Google sign-in failed: {exc}", status.HTTP_401_UNAUTHORIZED) from exc

    email = normalise_email(claims.get("email", ""))
    if not email or not claims.get("email_verified"):
        raise AuthError("Google did not return a verified email address.",
                        status.HTTP_401_UNAUTHORIZED)

    domain = settings.student_email_domain.strip().lower().lstrip("@")
    if domain and claims.get("hd", "").lower() != domain:
        raise AuthError(
            f"Only @{domain} Google accounts can sign in as a current student.",
            status.HTTP_403_FORBIDDEN,
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email)
        db.add(user)
    user.full_name = claims.get("name", user.full_name or "")
    user.account_type = STUDENT
    user.auth_provider = "google"
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


# --- dependencies ---


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the signed-in user, or None. Chat works either way."""
    if credentials is None:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("scope") != "user":
            return None
        user = db.get(User, int(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        return None
    return user if user and user.is_active else None


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise AuthError("Please sign in to continue.", status.HTTP_401_UNAUTHORIZED)
    return user


def require_student(user: User = Depends(require_user)) -> User:
    if user.account_type != STUDENT:
        raise AuthError(
            "This feature is for current students. Sign in with your UB email to use it.",
            status.HTTP_403_FORBIDDEN,
        )
    return user
