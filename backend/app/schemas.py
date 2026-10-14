from pydantic import BaseModel, Field, field_validator


class ChatQuery(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=64)


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = []
    confidence: float = 0.0
    intent: str = "question"
    trace: list[str] = []
    # True when the handbook had no confident answer, so the app offers "Ask an office".
    can_reroute: bool = False
    # Where the answer came from: label, file, page, the passage, and whether a page picture exists.
    citations: list[dict] = []


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str | None = Field(default=None, max_length=80)


# ---------- accounts ----------

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class SignupRequest(BaseModel):
    """Guest sign-up: any name and email, both required."""

    name: str = Field(min_length=1, max_length=80)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    # Omitted = the default starting password (settings.default_password).
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("name", "email", mode="before")
    @classmethod
    def strip_and_require(cls, value: object) -> object:
        # "   " would otherwise pass the length check and save a blank name.
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("This field is required.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    picture: str | None = None
    google_linked: bool = False
    default_password: bool = False
    # True for accounts outside the university domain (signed up with email).
    guest: bool = True
    # student | department | admin. Department accounts belong to one office.
    role: str = "student"
    office_id: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    created: bool = False


class AuthConfig(BaseModel):
    google_client_id: str
    google_domain: str
    default_password: str


# ---------- asking an office ----------


class OfficeList(BaseModel):
    offices: list[dict[str, str]]
    suggested: str | None = None


class TicketCreate(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    office_id: str = Field(min_length=1, max_length=40)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Please write your question.")
        return value


class TicketOut(BaseModel):
    ref: str
    office_id: str
    office_name: str
    question: str
    status: str
    answer: str | None = None
    answered_by: str | None = None
    created_at: str | None = None
    answered_at: str | None = None
