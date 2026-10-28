"""The query log: every student message and every reply, by conversation.

This is the DFD's "D3 Query Log" — the record reports on inquiry trends are built from.
Besides the raw turns, each handbook question gets one row in `inquiries`: who asked, its
topic, and whether the handbook answered it. The admin's inquiry report is built from those.
"""

from __future__ import annotations

import sqlite3
import threading
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

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
    user_id INTEGER,
    question TEXT NOT NULL,
    topic TEXT NOT NULL,
    answered INTEGER NOT NULL,
    source TEXT,
    confidence REAL NOT NULL DEFAULT 0,
    asked_at TEXT NOT NULL,
    replied_at TEXT NOT NULL,
    flagged_by TEXT,
    flagged_at TEXT,
    closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_inquiries_asked ON inquiries(asked_at);
"""


class Memory:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = db_path
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        # Added later: who asked, saved onto the question when their account is deleted, and when
        # the question was closed because of that deletion.
        columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(inquiries)")}
        for column in ("asker_name", "asker_email", "asker_department", "closed_at"):
            if column not in columns:
                self._connection.execute(f"ALTER TABLE inquiries ADD COLUMN {column} TEXT")
        self._connection.commit()

    def log_turn(self, session_id: str, role: str, message: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO conversation_turns (session_id, role, message) VALUES (?, ?, ?)",
                (session_id, role, message),
            )
            self._connection.commit()

    def recent_turns(self, session_id: str, limit: int = 6) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT role, message FROM conversation_turns WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return list(reversed(rows))

    def log_inquiry(
        self,
        session_id: str,
        user_id: int | None,
        question: str,
        topic: str,
        answered: bool,
        source: str | None,
        confidence: float,
        asked_at: str,
        replied_at: str,
        flagged_by: str | None = None,
    ) -> int:
        """`flagged_by`: set when the assistant flags the question itself (app/brain/moderation.py)."""
        flagged_at = replied_at if flagged_by else None
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO inquiries (session_id, user_id, question, topic, answered, source, "
                "confidence, asked_at, replied_at, flagged_by, flagged_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, user_id, question, topic, int(answered), source, confidence, asked_at, replied_at,
                 flagged_by, flagged_at),
            )
            self._connection.commit()
        return cursor.lastrowid

    def inquiries(self) -> list[sqlite3.Row]:
        """Every logged question, newest first."""
        with self._lock:
            return self._connection.execute("SELECT * FROM inquiries ORDER BY id DESC").fetchall()

    def inquiry(self, inquiry_id: int) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()

    def flag_inquiry(self, inquiry_id: int, by: str | None, at: str | None) -> None:
        """Mark a question offensive or off-topic; `by` None clears the mark."""
        with self._lock:
            self._connection.execute(
                "UPDATE inquiries SET flagged_by = ?, flagged_at = ? WHERE id = ?", (by, at, inquiry_id)
            )
            self._connection.commit()

    def activity_by_user(self) -> dict[int, tuple[int, str]]:
        """For each signed-in student: how many questions they asked, and when they last asked one."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT user_id, COUNT(*) AS n, MAX(asked_at) AS last FROM inquiries "
                "WHERE user_id IS NOT NULL GROUP BY user_id"
            ).fetchall()
        return {row["user_id"]: (row["n"], row["last"]) for row in rows}

    def for_users(self, user_ids: list[int]) -> list[sqlite3.Row]:
        with self._lock:
            return self._connection.execute(
                f"SELECT * FROM inquiries WHERE user_id IN ({','.join('?' * len(user_ids))})", user_ids
            ).fetchall()

    def close(self, inquiry_ids: list[int], at: str) -> None:
        """Mark questions Closed: their student's account was deleted while they were still open."""
        with self._lock:
            self._connection.executemany(
                "UPDATE inquiries SET closed_at = ? WHERE id = ? AND closed_at IS NULL",
                [(at, i) for i in inquiry_ids],
            )
            self._connection.commit()

    def keep_asker(self, askers: dict[int, tuple[str, str, str | None]]) -> None:
        """Before accounts are deleted: save each one's name, email and department onto its
        questions, so the report (and their department) still shows who asked.
        `askers` is {user_id: (name, email, department)}."""
        with self._lock:
            self._connection.executemany(
                "UPDATE inquiries SET asker_name = ?, asker_email = ?, asker_department = ?, user_id = NULL "
                "WHERE user_id = ?",
                [(name, email, department, user_id) for user_id, (name, email, department) in askers.items()],
            )
            self._connection.commit()

    def stats(self) -> dict:
        with self._lock:
            turns = self._connection.execute(
                "SELECT COUNT(*) AS n FROM conversation_turns"
            ).fetchone()["n"]
        return {"logged_turns": turns}


@lru_cache
def get_memory() -> Memory:
    """The one query log, shared by the brain and the admin report (works before the index is built)."""
    return Memory(get_settings().memory_db)
