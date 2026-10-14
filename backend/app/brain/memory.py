"""The query log: every student message and every reply, by conversation.

This is the DFD's "D3 Query Log" — the record reports on inquiry trends are built from.
`inquiries` keeps one row per handbook question with how it went, for the admin dashboard.
"""

from __future__ import annotations

import sqlite3
import threading
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
"""


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

    def inquiry_report(self, days: int, top: int = 8, gaps: int = 20) -> dict:
        """Questions over the last `days` days: totals, per day, most-cited pages, and the
        questions the handbook couldn't answer (where it may need more content), the same
        question asked again counted once, most-asked first."""
        since = (f"-{days - 1} days",)
        with self._lock:
            run = self._connection.execute
            totals = run(
                "SELECT COUNT(*) AS asked, COALESCE(SUM(answered), 0) AS answered FROM inquiries"
                " WHERE created_at >= date('now', ?)",
                since,
            ).fetchone()
            per_day = run(
                "SELECT date(created_at) AS day, COUNT(*) AS asked, SUM(answered) AS answered"
                " FROM inquiries WHERE created_at >= date('now', ?) GROUP BY day ORDER BY day",
                since,
            ).fetchall()
            sources = run(
                "SELECT source, COUNT(*) AS n FROM inquiries WHERE source IS NOT NULL"
                " AND created_at >= date('now', ?) GROUP BY source ORDER BY n DESC, source LIMIT ?",
                (*since, top),
            ).fetchall()
            unanswered = run(
                "SELECT MAX(question) AS question, COUNT(*) AS n, MAX(created_at) AS last_asked"
                " FROM inquiries WHERE answered = 0 AND created_at >= date('now', ?)"
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
                    "last_asked": f"{row['last_asked'].replace(' ', 'T')}Z",
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
