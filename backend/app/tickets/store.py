"""Tickets: one per question passed to an office or college. Lives in its own SQLite file."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    office_id TEXT NOT NULL,
    office_name TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    answer TEXT,
    answered_by TEXT,
    token_hash TEXT NOT NULL DEFAULT '',  -- from when offices answered through an emailed link; unused
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    answered_at TEXT,
    inquiry_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
"""


def _iso(timestamp: str | None) -> str | None:
    # SQLite's CURRENT_TIMESTAMP is UTC without a zone; say so, so browsers show local time.
    return f"{timestamp.replace(' ', 'T')}Z" if timestamp else None


@dataclass
class Ticket:
    id: int
    user_id: int
    office_id: str
    office_name: str
    question: str
    status: str
    answer: str | None
    answered_by: str | None
    created_at: str | None
    answered_at: str | None
    inquiry_id: int | None = None  # the chat question it came from, in the query log

    @property
    def ref(self) -> str:
        return f"UBT-{self.id:04d}"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Ticket":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            office_id=row["office_id"],
            office_name=row["office_name"],
            question=row["question"],
            status=row["status"],
            answer=row["answer"],
            answered_by=row["answered_by"],
            created_at=_iso(row["created_at"]),
            answered_at=_iso(row["answered_at"]),
            inquiry_id=row["inquiry_id"],
        )


def parse_ref(ref: str) -> int | None:
    if not ref.upper().startswith("UBT-"):
        return None
    try:
        return int(ref[4:])
    except ValueError:
        return None


class TicketStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        # Ticket files made before tickets were linked to chat questions.
        columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(tickets)")}
        if "inquiry_id" not in columns:
            self._connection.execute("ALTER TABLE tickets ADD COLUMN inquiry_id INTEGER")
        self._connection.commit()

    def create(
        self, user_id: int, office_id: str, office_name: str, question: str, inquiry_id: int | None = None
    ) -> Ticket:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO tickets (user_id, office_id, office_name, question, token_hash, inquiry_id)"
                " VALUES (?, ?, ?, ?, '', ?)",
                (user_id, office_id, office_name, question, inquiry_id),
            )
            self._connection.commit()
        return self.get(cursor.lastrowid)

    def get(self, ticket_id: int) -> Ticket | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return Ticket.from_row(row) if row else None

    def get_by_ref(self, ref: str) -> Ticket | None:
        ticket_id = parse_ref(ref)
        return self.get(ticket_id) if ticket_id is not None else None

    def for_user(self, user_id: int) -> list[Ticket]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC", (user_id,)
            ).fetchall()
        return [Ticket.from_row(row) for row in rows]

    def for_office(self, office_name: str | None = None) -> list[Ticket]:
        """The tickets sent to one office or college, newest first; with no name, every ticket."""
        with self._lock:
            if office_name is None:
                rows = self._connection.execute("SELECT * FROM tickets ORDER BY id DESC").fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT * FROM tickets WHERE office_name = ? ORDER BY id DESC", (office_name,)
                ).fetchall()
        return [Ticket.from_row(row) for row in rows]

    def by_inquiry(self) -> dict[int, Ticket]:
        """The latest ticket for each chat question that was sent to an office."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM tickets WHERE inquiry_id IS NOT NULL ORDER BY id"
            ).fetchall()
        return {row["inquiry_id"]: Ticket.from_row(row) for row in rows}

    def count_since(self, user_id: int, hours: int) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS n FROM tickets WHERE user_id = ? "
                "AND created_at >= datetime('now', ?)",
                (user_id, f"-{hours} hours"),
            ).fetchone()
        return row["n"]

    def answer(self, ticket_id: int, answer: str, answered_by: str) -> Ticket:
        with self._lock:
            self._connection.execute(
                "UPDATE tickets SET status = 'answered', answer = ?, answered_by = ?, "
                "answered_at = CURRENT_TIMESTAMP WHERE id = ?",
                (answer, answered_by or None, ticket_id),
            )
            self._connection.commit()
        return self.get(ticket_id)

    def delete(self, ticket_id: int) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
            self._connection.commit()
