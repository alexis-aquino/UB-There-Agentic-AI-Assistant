"""The query log: every student message and every reply, by conversation.

This is the DFD's "D3 Query Log" — the record reports on inquiry trends are built from.
`inquiries` keeps one row per handbook question with how it went, for the dashboards.
`document_checks` is the audit log of DFD process 4.0: one row per document photo checked
(the photo itself is never stored).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON conversation_turns(session_id);

CREATE TABLE IF NOT EXISTS inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answered INTEGER NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_inquiries_created ON inquiries(created_at);

CREATE TABLE IF NOT EXISTS document_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    status TEXT NOT NULL,
    missing TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_document_checks_created ON document_checks(created_at);
"""


def _iso(timestamp: str) -> str:
    # SQLite's CURRENT_TIMESTAMP is UTC without a zone; say so, so browsers show local time.
    return f"{timestamp.replace(' ', 'T')}Z"


class Memory:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = db_path
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    def log_turn(self, session_id: str, role: str, message: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO conversation_turns (session_id, role, message) VALUES (?, ?, ?)",
                (session_id, role, message),
            )
            self._connection.commit()

    def log_inquiry(
        self, session_id: str, question: str, answered: bool, confidence: float, source: str | None
    ) -> None:
        """One handbook question: did the handbook answer it, and which page led."""
        with self._lock:
            self._connection.execute(
                "INSERT INTO inquiries (session_id, question, answered, confidence, source)"
                " VALUES (?, ?, ?, ?, ?)",
                (session_id, question, int(answered), confidence, source),
            )
            self._connection.commit()

    def log_document_check(self, user_id: int, document_type: str, status: str, missing: list[str]) -> None:
        """One document photo checked (DFD 4.0's audit log): what it was and how it went."""
        with self._lock:
            self._connection.execute(
                "INSERT INTO document_checks (user_id, document_type, status, missing) VALUES (?, ?, ?, ?)",
                (user_id, document_type, status, json.dumps(missing)),
            )
            self._connection.commit()

    def query_log(
        self,
        days: int,
        search: str = "",
        include: Callable[[str], bool] | None = None,
        limit: int = 300,
    ) -> list[dict]:
        """The student query logs: each question and each document check over the last `days`
        days, newest first. `search` matches the question or document type; `include` keeps
        only the entries whose text it accepts (one office's, for its department)."""
        since = f"-{days - 1} days"
        like = f"%{search.strip().lower()}%"
        with self._lock:
            self._connection.create_function(
                "in_scope", 1, (lambda q: int(include(q))) if include else (lambda q: 1), deterministic=True
            )
            questions = self._connection.execute(
                "SELECT session_id, question, answered, source, created_at FROM inquiries"
                " WHERE created_at >= date('now', ?) AND lower(question) LIKE ? AND in_scope(question)"
                " ORDER BY id DESC LIMIT ?",
                (since, like, limit),
            ).fetchall()
            checks = self._connection.execute(
                "SELECT user_id, document_type, status, missing, created_at FROM document_checks"
                " WHERE created_at >= date('now', ?) AND lower(document_type) LIKE ? AND in_scope(document_type)"
                " ORDER BY id DESC LIMIT ?",
                (since, like, limit),
            ).fetchall()

        def user_of(session_id: str) -> int | None:
            # Chat sessions are "<user id>:<the browser's session id>" (see routers/chat.py).
            head = session_id.split(":", 1)[0]
            return int(head) if head.isdigit() and ":" in session_id else None

        entries = [
            {
                "kind": "question",
                "at": _iso(row["created_at"]),
                "user_id": user_of(row["session_id"]),
                "text": row["question"],
                "outcome": "answered" if row["answered"] else "not_found",
                "source": row["source"],
                "missing": [],
            }
            for row in questions
        ] + [
            {
                "kind": "document",
                "at": _iso(row["created_at"]),
                "user_id": row["user_id"],
                "text": row["document_type"],
                "outcome": row["status"],
                "source": None,
                "missing": json.loads(row["missing"]),
            }
            for row in checks
        ]
        entries.sort(key=lambda e: e["at"], reverse=True)
        return entries[:limit]

    def inquiry_report(
        self,
        days: int,
        top: int = 8,
        gaps: int = 20,
        include: Callable[[str], bool] | None = None,
    ) -> dict:
        """Questions over the last `days` days: totals, per day, most-cited pages, and the
        questions the handbook couldn't answer (where it may need more content), the same
        question asked again counted once, most-asked first.

        `include` narrows the report to the questions it accepts (one office's, for its
        department dashboard). It runs at report time, so older questions count too."""
        since = (f"-{days - 1} days",)
        with self._lock:
            # Every query below filters on in_scope(question).
            self._connection.create_function(
                "in_scope", 1, (lambda q: int(include(q))) if include else (lambda q: 1), deterministic=True
            )
            run = self._connection.execute
            totals = run(
                "SELECT COUNT(*) AS asked, COALESCE(SUM(answered), 0) AS answered FROM inquiries"
                " WHERE in_scope(question) AND created_at >= date('now', ?)",
                since,
            ).fetchone()
            per_day = run(
                "SELECT date(created_at) AS day, COUNT(*) AS asked, SUM(answered) AS answered"
                " FROM inquiries WHERE in_scope(question) AND created_at >= date('now', ?)"
                " GROUP BY day ORDER BY day",
                since,
            ).fetchall()
            sources = run(
                "SELECT source, COUNT(*) AS n FROM inquiries WHERE source IS NOT NULL"
                " AND in_scope(question) AND created_at >= date('now', ?)"
                " GROUP BY source ORDER BY n DESC, source LIMIT ?",
                (*since, top),
            ).fetchall()
            unanswered = run(
                "SELECT MAX(question) AS question, COUNT(*) AS n, MAX(created_at) AS last_asked"
                " FROM inquiries WHERE answered = 0 AND in_scope(question) AND created_at >= date('now', ?)"
                " GROUP BY lower(trim(question)) ORDER BY n DESC, last_asked DESC LIMIT ?",
                (*since, gaps),
            ).fetchall()
            first_day = run("SELECT date('now', ?) AS day", since).fetchone()["day"]

        # Every day in the window, including quiet ones, so a chart has no holes.
        counts = {row["day"]: row for row in per_day}
        start = date.fromisoformat(first_day)
        days_out = []
        for offset in range(days):
            day = (start + timedelta(days=offset)).isoformat()
            row = counts.get(day)
            days_out.append(
                {"day": day, "asked": row["asked"] if row else 0, "answered": row["answered"] if row else 0}
            )
        return {
            "days": days,
            "asked": totals["asked"],
            "answered": totals["answered"],
            "per_day": days_out,
            "top_sources": [{"source": row["source"], "count": row["n"]} for row in sources],
            "unanswered": [
                {
                    "question": row["question"],
                    "count": row["n"],
                    "last_asked": _iso(row["last_asked"]),
                }
                for row in unanswered
            ],
        }

    def recent_turns(self, session_id: str, limit: int = 6) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT role, message FROM conversation_turns WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return list(reversed(rows))

    def stats(self) -> dict:
        with self._lock:
            turns = self._connection.execute(
                "SELECT COUNT(*) AS n FROM conversation_turns"
            ).fetchone()["n"]
        return {"logged_turns": turns}
