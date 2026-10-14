"""The users table. Lives in its own SQLite file, apart from the brain's memory."""

from __future__ import annotations

import secrets
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from app.auth.security import hash_password, verify_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    google_sub TEXT UNIQUE,
    picture TEXT,
    default_password INTEGER NOT NULL DEFAULT 1,
    role TEXT NOT NULL DEFAULT 'student',
    office_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# student: everyone by default (guests too). department: staff of one office (office_id).
# admin: the whole system.
ROLES = ("student", "department", "admin")

# Columns added after the first release; older users.db files get them on startup.
MIGRATIONS = {
    "role": "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'",
    "office_id": "ALTER TABLE users ADD COLUMN office_id TEXT",
}


class EmailTakenError(Exception):
    pass


class UnknownUserError(Exception):
    pass


@dataclass
class User:
    id: int
    email: str
    name: str
    picture: str | None
    google_linked: bool
    default_password: bool
    role: str = "student"
    office_id: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            picture=row["picture"],
            google_linked=row["google_sub"] is not None,
            default_password=bool(row["default_password"]),
            role=row["role"],
            office_id=row["office_id"],
        )


class UserStore:
    def __init__(self, db_path: Path, default_password: str) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_password = default_password
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        self._migrate()
        self._connection.commit()
        self.secret = self._signing_secret()

    def _migrate(self) -> None:
        columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(users)")}
        for column, sql in MIGRATIONS.items():
            if column not in columns:
                self._connection.execute(sql)

    def _signing_secret(self) -> str:
        """Generated once and kept in the db, so sessions survive restarts."""
        with self._lock:
            row = self._connection.execute(
                "SELECT value FROM meta WHERE key = 'token_secret'"
            ).fetchone()
            if row:
                return row["value"]
            secret = secrets.token_urlsafe(48)
            self._connection.execute(
                "INSERT INTO meta (key, value) VALUES ('token_secret', ?)", (secret,)
            )
            self._connection.commit()
            return secret

    def _one(self, sql: str, params: tuple) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute(sql, params).fetchone()

    def get(self, user_id: int) -> User | None:
        row = self._one("SELECT * FROM users WHERE id = ?", (user_id,))
        return User.from_row(row) if row else None

    def create(
        self,
        email: str,
        name: str,
        password: str | None = None,
        google_sub: str | None = None,
        picture: str | None = None,
    ) -> User:
        password = password or self.default_password
        try:
            with self._lock:
                cursor = self._connection.execute(
                    "INSERT INTO users (email, name, password_hash, google_sub, picture, default_password)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        email.strip(),
                        name.strip(),
                        hash_password(password),
                        google_sub,
                        picture,
                        int(password == self.default_password),
                    ),
                )
                self._connection.commit()
        except sqlite3.IntegrityError as exc:
            raise EmailTakenError(email) from exc
        return self.get(cursor.lastrowid)

    def authenticate(self, email: str, password: str) -> User | None:
        row = self._one("SELECT * FROM users WHERE email = ?", (email.strip(),))
        if row and verify_password(password, row["password_hash"]):
            return User.from_row(row)
        return None

    def sign_in_with_google(
        self, google_sub: str, email: str, name: str, picture: str | None
    ) -> tuple[User, bool]:
        """Find or create the account for a verified Google identity. Returns (user, created).

        An existing email/password account with the same verified email is linked rather than
        duplicated, so one person keeps one account however they sign in.
        """
        row = self._one("SELECT * FROM users WHERE google_sub = ?", (google_sub,))
        if row:
            return User.from_row(row), False

        row = self._one("SELECT * FROM users WHERE email = ?", (email,))
        if row:
            with self._lock:
                self._connection.execute(
                    "UPDATE users SET google_sub = ?, picture = COALESCE(picture, ?) WHERE id = ?",
                    (google_sub, picture, row["id"]),
                )
                self._connection.commit()
            return self.get(row["id"]), False

        return self.create(email, name, google_sub=google_sub, picture=picture), True

    def change_password(self, user_id: int, current: str, new: str) -> bool:
        row = self._one("SELECT * FROM users WHERE id = ?", (user_id,))
        if not row or not verify_password(current, row["password_hash"]):
            return False
        with self._lock:
            self._connection.execute(
                "UPDATE users SET password_hash = ?, default_password = ? WHERE id = ?",
                (hash_password(new), int(new == self.default_password), user_id),
            )
            self._connection.commit()
        return True

    def set_role(self, email: str, role: str, office_id: str | None = None) -> User:
        """Make an account a student, an office's staff, or an admin."""
        if role not in ROLES:
            raise ValueError(f"Unknown role {role!r}; use one of {', '.join(ROLES)}.")
        if (role == "department") != bool(office_id):
            raise ValueError("Department accounts need an office; other roles must not have one.")
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE users SET role = ?, office_id = ? WHERE email = ?",
                (role, office_id, email.strip()),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise UnknownUserError(email)
        return self.get_by_email(email)

    def all(self) -> list[User]:
        with self._lock:
            rows = self._connection.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [User.from_row(row) for row in rows]

    def get_by_email(self, email: str) -> User | None:
        row = self._one("SELECT * FROM users WHERE email = ?", (email.strip(),))
        return User.from_row(row) if row else None
