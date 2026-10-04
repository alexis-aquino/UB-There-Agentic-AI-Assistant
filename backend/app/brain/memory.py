"""The query log: every student message and every reply, by conversation.

This is the DFD's "D3 Query Log" — the record reports on inquiry trends are built from.
"""

from __future__ import annotations

import sqlite3
import threading
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
