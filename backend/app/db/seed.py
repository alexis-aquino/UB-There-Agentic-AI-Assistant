"""First-run setup: departments and a superadmin account."""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Admin
from app.services.auth import SUPERADMIN, hash_password
from app.services.router_agent import seed_departments


def seed(db: Session) -> list[str]:
    """Returns notes to print at startup. Safe to call on every boot."""
    notes: list[str] = []
    settings = get_settings()

    created = seed_departments(db)
    if created:
        notes.append(
            f"Seeded {created} departments with PLACEHOLDER email addresses — "
            "set real ones in the admin dashboard before enabling live mail."
        )

    if db.query(Admin).count() == 0:
        password = settings.seed_admin_password or secrets.token_urlsafe(12)
        db.add(
            Admin(
                username=settings.seed_admin_username,
                password_hash=hash_password(password),
                full_name="Initial superadmin",
                role=SUPERADMIN,
            )
        )
        db.commit()
        notes.append(
            "Created the first admin account:\n"
            f"    username: {settings.seed_admin_username}\n"
            f"    password: {password}\n"
            "  This password is shown once. Save it now."
        )

    return notes
