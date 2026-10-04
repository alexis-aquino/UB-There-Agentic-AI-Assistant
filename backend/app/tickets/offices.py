"""The offices a question can be passed to, read from backend/offices.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class Office:
    id: str
    name: str
    email: str
    keywords: tuple[str, ...]


def load_offices() -> list[Office]:
    path = get_settings().offices_path
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Office(
            id=item["id"],
            name=item["name"],
            email=item["email"],
            keywords=tuple(k.lower() for k in item.get("keywords", [])),
        )
        for item in data.get("offices", [])
    ]


def get_office(office_id: str) -> Office | None:
    return next((office for office in load_offices() if office.id == office_id), None)


def suggest_office(question: str) -> str | None:
    """The office whose keywords best match the question; the first office if none match."""
    offices = load_offices()
    if not offices:
        return None
    words = re.findall(r"[a-z]+", question.lower())

    def score(office: Office) -> int:
        # "enrolling" matches "enroll"; short keywords like "id" must match exactly.
        return sum(
            1
            for word in words
            for keyword in office.keywords
            if word == keyword or (len(keyword) >= 4 and word.startswith(keyword))
        )

    best = max(offices, key=score)
    return best.id if score(best) > 0 else offices[0].id
