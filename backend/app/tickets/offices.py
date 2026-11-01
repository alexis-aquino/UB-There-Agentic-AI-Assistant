"""Where a question can be sent: the offices in backend/offices.json and the colleges in
backend/departments.json, plus any typed in under "Other" at sign-up once an administrator approved
the account. Each one answers in the dashboard, through its University department account (the
account's department is the office's or college's name)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.auth.departments import load_departments
from app.config import get_settings


@dataclass(frozen=True)
class Office:
    id: str
    name: str
    keywords: tuple[str, ...] = ()
    kind: str = "office"  # office | department (a college)


def _listed_offices() -> list[Office]:
    path = get_settings().offices_path
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return [
        Office(
            id=item["id"],
            name=item["name"],
            keywords=tuple(k.lower() for k in item.get("keywords", [])),
        )
        for item in data.get("offices", [])
    ]


def _typed_in(kind: str, listed: set[str]) -> list[str]:
    """Names typed in under Other as `kind`, from approved accounts, that aren't listed already."""
    from app.routers.auth import get_store  # here, since the auth router imports this module

    return [name for name in get_store().approved_units(kind) if name not in listed]


def load_offices() -> list[Office]:
    """The offices in offices.json, then the typed-in offices (a typed-in one's id is its name)."""
    listed = _listed_offices()
    known = {office.name for office in listed} | set(load_departments())
    return listed + [Office(id=name, name=name) for name in _typed_in("office", known)]


def all_departments() -> list[str]:
    """The colleges in departments.json, then the typed-in departments. Students choose from these."""
    listed = load_departments()
    known = set(listed) | {office.name for office in _listed_offices()}
    return listed + _typed_in("department", known)


def is_listed(name: str) -> bool:
    """A college or office from departments.json / offices.json, not one typed in under Other."""
    return name in load_departments() or name in {office.name for office in _listed_offices()}


def load_recipients() -> list[Office]:
    """The offices, then the departments. A department's id is its name."""
    return load_offices() + [Office(id=name, name=name, kind="department") for name in all_departments()]


def get_office(office_id: str) -> Office | None:
    return next((office for office in load_recipients() if office.id == office_id), None)


def suggest_office(question: str, department: str | None = None) -> str | None:
    """The office whose keywords best match the question. If none match, the student's own college
    (`department`), else the first office."""
    offices = load_offices()
    words = re.findall(r"[a-z]+", question.lower())

    def score(office: Office) -> int:
        # "enrolling" matches "enroll"; short keywords like "id" must match exactly.
        return sum(
            1
            for word in words
            for keyword in office.keywords
            if word == keyword or (len(keyword) >= 4 and word.startswith(keyword))
        )

    best = max(offices, key=score, default=None)
    if best and score(best) > 0:
        return best.id
    if department and department in all_departments():
        return department
    return offices[0].id if offices else None
