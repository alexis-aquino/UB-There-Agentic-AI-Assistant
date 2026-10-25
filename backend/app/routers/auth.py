from dataclasses import asdict
from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException

from app.auth.google import GoogleTokenError, verify_id_token
from app.auth.security import issue_token, read_token
from app.auth.store import EmailTakenError, User, UserStore
from app.config import get_settings
from app.schemas import (
    AuthConfig,
    AuthResponse,
    ChangePasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    SignupRequest,
    UserOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@lru_cache
def get_store() -> UserStore:
    settings = get_settings()
    return UserStore(settings.users_db, settings.default_password)


def _in_domain(email: str) -> bool:
    domain = get_settings().google_domain
    return bool(domain) and email.lower().endswith(f"@{domain.lower()}")


def is_admin(user: User) -> bool:
    # A UB address on the admin list. Guest accounts can't be admins even if listed, and with
    # Google sign-in on, UB addresses can only be made through Google.
    return _in_domain(user.email) and user.email.lower() in get_settings().admins


def _user_out(user: User) -> UserOut:
    return UserOut(**asdict(user), guest=not _in_domain(user.email), admin=is_admin(user))


DISABLED = "This account has been disabled by an administrator."


def _session(user: User, created: bool = False) -> AuthResponse:
    if user.disabled:
        raise HTTPException(status_code=403, detail=DISABLED)
    get_store().touch(user.id)
    token = issue_token(user.id, get_store().secret, get_settings().session_days)
    return AuthResponse(token=token, user=_user_out(user), created=created)


def current_user(authorization: str = Header(default="")) -> User:
    scheme, _, token = authorization.partition(" ")
    user_id = read_token(token, get_store().secret) if scheme.lower() == "bearer" else None
    user = get_store().get(user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    if user.disabled:
        # 401, so the app signs them out at once.
        raise HTTPException(status_code=401, detail=DISABLED)
    return user


def optional_user(authorization: str = Header(default="")) -> User | None:
    """The signed-in user, or None: for routes that also work without signing in."""
    try:
        return current_user(authorization)
    except HTTPException:
        return None


def admin_user(user: User = Depends(current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only administrators can see this.")
    return user


@router.get("/config", response_model=AuthConfig)
def config() -> AuthConfig:
    settings = get_settings()
    return AuthConfig(
        google_client_id=settings.google_client_id,
        google_domain=settings.google_domain,
        default_password=settings.default_password,
    )


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(body: SignupRequest) -> AuthResponse:
    settings = get_settings()
    # With Google sign-in on, university addresses must come through Google, so nobody can
    # claim a @ub.edu.ph identity by typing it into the guest form.
    if settings.google_client_id and _in_domain(body.email):
        raise HTTPException(
            status_code=400,
            detail=f"@{settings.google_domain} accounts sign in with Google. "
            "Use the Google button above.",
        )
    try:
        user = get_store().create(body.email, body.name, body.password)
    except EmailTakenError as exc:
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
    return _session(user, created=True)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest) -> AuthResponse:
    user = get_store().authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return _session(user)


@router.post("/google", response_model=AuthResponse)
def google(body: GoogleLoginRequest) -> AuthResponse:
    try:
        settings = get_settings()
        identity = verify_id_token(
            body.credential, settings.google_client_id, settings.google_domain
        )
    except GoogleTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user, created = get_store().sign_in_with_google(
        identity.sub, identity.email, identity.name, identity.picture
    )
    return _session(user, created=created)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    get_store().touch(user.id)  # each time the app is opened
    return _user_out(user)


@router.post("/password", response_model=UserOut)
def change_password(body: ChangePasswordRequest, user: User = Depends(current_user)) -> UserOut:
    if not get_store().change_password(user.id, body.current_password, body.new_password):
        raise HTTPException(status_code=400, detail="Your current password is incorrect.")
    return _user_out(get_store().get(user.id))
