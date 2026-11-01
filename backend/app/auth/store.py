"""The users table. Lives in its own SQLite file, apart from the brain's memory."""

from __future__ import annotations

import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- University department sign-ups an administrator rejected. The account itself is deleted; this is
-- kept only so signing in with it says why, and goes when the address signs up again.
CREATE TABLE IF NOT EXISTS rejections (
    email TEXT PRIMARY KEY COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    department TEXT,
    rejected_by TEXT NOT NULL,
    rejected_at TEXT NOT NULL
);
"""


# Added after the first release; older users.db files get them on startup.
COLUMNS = {
    "last_active_at": "TEXT",  # last sign-in or visit, ISO UTC
    "disabled_by": "TEXT",  # the administrator who disabled the account; NULL = enabled
    "disabled_at": "TEXT",
    # student | guest | department. NULL on accounts made before account types: those count as
    # students when they're UB addresses, guests otherwise (app/routers/auth.py, kind_of).
    "account_type": "TEXT",
    "department": "TEXT",  # students and university departments
    "approved_by": "TEXT",  # university departments: the administrator who let them in
    "approved_at": "TEXT",
    # University department accounts that typed in their own (Other): department | office. NULL when
    # they chose a listed college or office, whose kind is known from departments.json / offices.json.
    "unit_kind": "TEXT",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class EmailTakenError(Exception):
    pass


@dataclass
class User:
    id: int
    email: str
    name: str
    picture: str | None
    google_linked: bool
    default_password: bool
    disabled: bool = False  # by an administrator: can't sign in
    account_type: str | None = None
    department: str | None = None
    approved: bool = False  # university departments only: an administrator approved the account

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            picture=row["picture"],
            google_linked=row["google_sub"] is not None,
            default_password=bool(row["default_password"]),
            disabled=row["disabled_by"] is not None,
            account_type=row["account_type"],
            department=row["department"],
            approved=row["approved_by"] is not None,
        )


class UserStore:
    def __init__(self, db_path: Path, default_password: str) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_password = default_password
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        existing = {row["name"] for row in self._connection.execute("PRAGMA table_info(users)")}
        for column, kind in COLUMNS.items():
            if column not in existing:
                self._connection.execute(f"ALTER TABLE users ADD COLUMN {column} {kind}")
        self._connection.commit()
        self.secret = self._signing_secret()

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
        account_type: str | None = None,
        department: str | None = None,
        unit_kind: str | None = None,
    ) -> User:
        password = password or self.default_password
        try:
            with self._lock:
                cursor = self._connection.execute(
                    "INSERT INTO users (email, name, password_hash, google_sub, picture, default_password,"
                    " account_type, department, unit_kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        email.strip(),
                        name.strip(),
                        hash_password(password),
                        google_sub,
                        picture,
                        int(password == self.default_password),
                        account_type,
                        department,
                        unit_kind,
                    ),
                )
                # Signing up again replaces an earlier rejected sign-up.
                self._connection.execute("DELETE FROM rejections WHERE email = ?", (email.strip(),))
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

    def rename(self, user_id: int, name: str) -> None:
        with self._lock:
            self._connection.execute("UPDATE users SET name = ? WHERE id = ?", (name.strip(), user_id))
            self._connection.commit()

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

    # ---------- account management (admin dashboard) ----------

    def touch(self, user_id: int) -> None:
        """Note that the account was just used, for "last used" on the admin's Accounts page."""
        with self._lock:
            self._connection.execute("UPDATE users SET last_active_at = ? WHERE id = ?", (now_iso(), user_id))
            self._connection.commit()

    def all_rows(self) -> list[sqlite3.Row]:
        """Every account, with the columns the admin's Accounts page shows (never the password hash)."""
        with self._lock:
            return self._connection.execute(
                "SELECT id, email, name, google_sub IS NOT NULL AS google_linked, created_at, "
                "last_active_at, disabled_by, disabled_at, account_type, department, approved_by, approved_at, "
                "unit_kind FROM users ORDER BY id"
            ).fetchall()

    def approved_units(self, kind: str) -> list[str]:
        """The departments or offices (`kind`) of approved, enabled University department accounts.
        No kind counts as an office: a name typed in before the kind was asked. Listed colleges and
        offices are in here too; the caller drops them."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT DISTINCT department FROM users WHERE account_type = 'department' "
                "AND (unit_kind = ? OR (unit_kind IS NULL AND ? = 'office')) "
                "AND approved_by IS NOT NULL AND disabled_by IS NULL AND department IS NOT NULL ORDER BY department",
                (kind, kind),
            ).fetchall()
        return [row["department"] for row in rows]

    def set_disabled(self, user_ids: list[int], by: str | None) -> None:
        """Disable the accounts (by an administrator's name), or enable them again with `by` None.
        Disabling an account that is already disabled keeps the original date."""
        with self._lock:
            for user_id in user_ids:
                if by is None:
                    self._connection.execute(
                        "UPDATE users SET disabled_by = NULL, disabled_at = NULL WHERE id = ?", (user_id,)
                    )
                else:
                    self._connection.execute(
                        "UPDATE users SET disabled_by = ?, disabled_at = ? WHERE id = ? AND disabled_by IS NULL",
                        (by, now_iso(), user_id),
                    )
            self._connection.commit()

    def approve(self, user_ids: list[int], by: str) -> None:
        """Let university department accounts in. Only accounts signed up as departments."""
        with self._lock:
            self._connection.executemany(
                "UPDATE users SET approved_by = ?, approved_at = ? "
                "WHERE id = ? AND account_type = 'department' AND approved_by IS NULL",
                [(by, now_iso(), i) for i in user_ids],
            )
            self._connection.commit()

    def pending(self, user_ids: list[int]) -> list[int]:
        """Those of `user_ids` that are University department accounts still waiting for approval."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT id FROM users WHERE account_type = 'department' AND approved_by IS NULL"
            ).fetchall()
        waiting = {row["id"] for row in rows}
        return [i for i in user_ids if i in waiting]

    def reject(self, user_ids: list[int], by: str) -> None:
        """Delete University department sign-ups still waiting for approval, keeping a note of each
        rejection so the person is told why when they next sign in."""
        ids = self.pending(user_ids)
        with self._lock:
            self._connection.executemany(
                "INSERT OR REPLACE INTO rejections (email, password_hash, department, rejected_by, rejected_at) "
                "SELECT email, password_hash, department, ?, ? FROM users WHERE id = ?",
                [(by, now_iso(), i) for i in ids],
            )
            self._connection.executemany("DELETE FROM users WHERE id = ?", [(i,) for i in ids])
            self._connection.commit()

    def rejection(self, email: str, password: str) -> sqlite3.Row | None:
        """The rejected sign-up with this email, only for someone who knows its password."""
        row = self._one("SELECT * FROM rejections WHERE email = ?", (email.strip(),))
        return row if row and verify_password(password, row["password_hash"]) else None

    def delete(self, user_ids: list[int]) -> None:
        with self._lock:
            self._connection.executemany("DELETE FROM users WHERE id = ?", [(i,) for i in user_ids])
            self._connection.commit()
