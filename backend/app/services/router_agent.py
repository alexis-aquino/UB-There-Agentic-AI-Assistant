"""Decides which university office an unanswered question belongs to.

Keyword matching rather than an LLM call: routing must be auditable and must not change
between runs, since a misrouted inquiry wastes a real person's time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Department

# Seeded when the database is empty. Emails are placeholders on purpose — they must be
# replaced with real office addresses before MAIL_MODE is ever switched to live.
DEFAULT_DEPARTMENTS = [
    {
        "name": "Office of the Registrar",
        "email": "registrar@example-ub.edu.ph",
        "keywords": "grade,grades,transcript,enrollment,enrolment,enrol,registration,subject,"
        "drop,dropping,units,overload,shifting,credential,record,graduation,diploma",
        "is_fallback": True,
    },
    {
        "name": "Cash Management Office",
        "email": "cashier@example-ub.edu.ph",
        "keywords": "tuition,fee,fees,payment,balance,refund,receipt,billing,installment,"
        "scholarship,discount,assessment",
        "is_fallback": False,
    },
    {
        "name": "Admissions Office",
        "email": "admissions@example-ub.edu.ph",
        "keywords": "admission,entrance,exam,apply,application,requirements,transferee,"
        "freshman,incoming,enrol new,shift",
        "is_fallback": False,
    },
    {
        "name": "Office of Student Affairs",
        "email": "osa@example-ub.edu.ph",
        "keywords": "uniform,conduct,discipline,organization,event,activity,id,violation,"
        "guidance,counseling,clinic,health,scholar",
        "is_fallback": False,
    },
    {
        "name": "Information Technology Center",
        "email": "itc@example-ub.edu.ph",
        "keywords": "portal,account,password,login,slims,email,wifi,system,access,online",
        "is_fallback": False,
    },
]


@dataclass
class RoutingDecision:
    department: Department | None
    reason: str


def seed_departments(db: Session) -> int:
    if db.query(Department).count() > 0:
        return 0
    for entry in DEFAULT_DEPARTMENTS:
        db.add(Department(**entry))
    db.commit()
    return len(DEFAULT_DEPARTMENTS)


def route(db: Session, question: str) -> RoutingDecision:
    departments = db.query(Department).all()
    if not departments:
        return RoutingDecision(None, "No departments are configured.")

    words = set(re.findall(r"[a-z]+", question.lower()))

    best: Department | None = None
    best_hits: list[str] = []
    for department in departments:
        hits = [kw for kw in department.keyword_list() if kw in words]
        if len(hits) > len(best_hits):
            best, best_hits = department, hits

    if best and best_hits:
        return RoutingDecision(
            best, f"Matched {best.name} on: {', '.join(sorted(best_hits))}."
        )

    fallback = next((d for d in departments if d.is_fallback), departments[0])
    return RoutingDecision(
        fallback, f"No keyword matched; routed to the fallback office ({fallback.name})."
    )
