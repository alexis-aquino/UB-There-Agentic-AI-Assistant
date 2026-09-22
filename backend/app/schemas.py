from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# A typo here means escalations are mailed into the void, so the shape is checked.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# --- chat ---


class ChatQuery(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=64)
    student_email: str = Field(default="", max_length=200)
    student_name: str = Field(default="", max_length=160)


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = []
    confidence: float = 0.0
    escalated: bool = False
    reference_code: str | None = None
    department: str | None = None


# --- admin auth ---


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    department: str | None = None


# --- admin views ---


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    keywords: str
    is_fallback: bool


class DepartmentUpdate(BaseModel):
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN)
    keywords: str | None = None


class InquiryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    confidence: float
    sources: str
    escalated: bool
    created_at: datetime


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_code: str
    question: str
    student_email: str
    student_name: str
    confidence: float
    partial_answer: str
    routing_reason: str
    status: str
    delivery_mode: str
    delivered: bool
    delivery_error: str
    rendered_email: str
    resolution_note: str
    created_at: datetime
    updated_at: datetime
    department_name: str | None = None


class EscalationUpdate(BaseModel):
    status: str | None = None
    resolution_note: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    size_bytes: int
    uploaded_by: str
    chunk_count: int
    indexed_at: datetime | None
    created_at: datetime


# --- public tracking ---


class TrackingOut(BaseModel):
    reference_code: str
    question: str
    status: str
    department: str | None
    created_at: datetime
    updated_at: datetime
    resolution_note: str


# --- document auditing ---


class AuditFinding(BaseModel):
    check: str
    passed: bool
    detail: str
    how_to_fix: str = ""


class AuditResponse(BaseModel):
    filename: str
    passed: bool
    form_type: str
    sharpness: float
    width: int
    height: int
    findings: list[AuditFinding]
    extracted_text: str = ""
    ocr_available: bool = True


# --- student / guest auth ---


class GuestSignIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=200)


class StudentRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    student_number: str = Field(default="", max_length=40)


class StudentLogin(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class GoogleSignIn(BaseModel):
    id_token: str = Field(min_length=10)


class UserTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    full_name: str
    account_type: str
    auth_provider: str = "local"


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
