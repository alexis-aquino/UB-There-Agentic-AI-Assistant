"""Relational schema.

Written against SQLAlchemy so the same models run on SQLite during development and on
PostgreSQL for deployment — only DATABASE_URL changes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    email: Mapped[str] = mapped_column(String(200))
    # Comma-separated terms matched against a question to route it here.
    keywords: Mapped[str] = mapped_column(Text, default="")
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    escalations: Mapped[list["Escalation"]] = relationship(back_populates="department")

    def keyword_list(self) -> list[str]:
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160), default="")
    # "superadmin" sees everything; "department_admin" sees only its own department.
    role: Mapped[str] = mapped_column(String(40), default="department_admin")
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    department: Mapped[Department | None] = relationship()


class Inquiry(Base):
    """Every question asked, for the admin query log and inquiry-trend analysis."""

    __tablename__ = "inquiries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), default="")
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sources: Mapped[str] = mapped_column(Text, default="")
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    student_email: Mapped[str] = mapped_column(String(200), default="")
    student_name: Mapped[str] = mapped_column(String(160), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    partial_answer: Mapped[str] = mapped_column(Text, default="")

    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    routing_reason: Mapped[str] = mapped_column(Text, default="")

    # new -> sent -> acknowledged -> resolved
    status: Mapped[str] = mapped_column(String(32), default="new")
    # "dry_run" records without sending; "live" actually delivered.
    delivery_mode: Mapped[str] = mapped_column(String(16), default="dry_run")
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_error: Mapped[str] = mapped_column(Text, default="")
    rendered_email: Mapped[str] = mapped_column(Text, default="")
    resolution_note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    department: Mapped[Department | None] = relationship(back_populates="escalations")


class Document(Base):
    """Files in the knowledge base, so admins can see what the chatbot actually knows."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(String(64), default="")
    uploaded_by: Mapped[str] = mapped_column(String(80), default="")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    session_id: Mapped[str] = mapped_column(String(64), default="")
    form_type: Mapped[str] = mapped_column(String(80), default="generic")
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    sharpness: Mapped[float] = mapped_column(Float, default=0.0)
    findings: Mapped[str] = mapped_column(Text, default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    """Students and guests.

    Guests (prospective students) give a name and email only — no password, since
    requiring one would deter the exact people the paper wants to reach. Current
    students authenticate with their UB Google Workspace address, either with a
    password or through Sign in with Google.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    # "guest" = prospective student, "student" = current student
    account_type: Mapped[str] = mapped_column(String(20), default="guest")
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    auth_provider: Mapped[str] = mapped_column(String(20), default="local")  # local | google
    student_number: Mapped[str] = mapped_column(String(40), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
