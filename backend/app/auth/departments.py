"""The university's departments, read from backend/departments.json."""

from __future__ import annotations

import json

from app.config import get_settings


def load_departments() -> list[str]:
    path = get_settings().departments_path
    if not path.exists():
        return []
    return [str(name) for name in json.loads(path.read_text(encoding="utf-8")).get("departments", [])]
