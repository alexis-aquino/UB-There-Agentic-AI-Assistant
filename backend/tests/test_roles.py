"""Roles (guest / student / department / admin) and which endpoints need a signed-in account."""

import sqlite3
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import set_role
from accounts import headers_for
from app.auth.store import UnknownUserError, UserStore
from app.brain import engine
from app.main import app
from app.routers import auth
from app.routers import chat as chat_router

client = TestClient(app)


def new_email():
    return f"r-{uuid.uuid4().hex[:8]}@example.com"


def test_form_sign_ups_are_guests():
    token = client.post("/api/auth/signup", json={"name": "Ivy", "email": new_email()}).json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["role"] == "guest" and me["guest"] is True and me["office_id"] is None


def test_university_google_sign_ins_are_students():
    user, _ = auth.get_store().sign_in_with_google(uuid.uuid4().hex, f"s-{uuid.uuid4().hex[:6]}@ub.edu.ph", "Sam", None)
    assert user.role == "student"


def test_a_guest_who_links_google_becomes_a_student_but_staff_keep_their_role():
    store = auth.get_store()
    guest, staff = new_email(), new_email()
    store.create(guest, "Gil")
    store.create(staff, "Sol")
    store.set_role(staff, "department", "registrar")
    assert store.sign_in_with_google(uuid.uuid4().hex, guest, "Gil", None)[0].role == "student"
    assert store.sign_in_with_google(uuid.uuid4().hex, staff, "Sol", None)[0].role == "department"


def test_set_role_shows_on_the_account():
    email = new_email()
    auth.get_store().create(email, "Jo")
    user = auth.get_store().set_role(email, "department", "registrar")
    assert (user.role, user.office_id) == ("department", "registrar")

    user = auth.get_store().set_role(email, "admin")
    assert (user.role, user.office_id) == ("admin", None)


@pytest.mark.parametrize(
    ("role", "office_id"),
    [("owner", None), ("department", None), ("admin", "registrar"), ("student", "registrar")],
)
def test_set_role_refuses_bad_combinations(role, office_id):
    email = new_email()
    auth.get_store().create(email, "Kai")
    with pytest.raises(ValueError):
        auth.get_store().set_role(email, role, office_id)


def test_set_role_on_a_missing_account():
    with pytest.raises(UnknownUserError):
        auth.get_store().set_role(new_email(), "admin")


def test_old_users_db_gets_the_role_columns(tmp_path):
    """A users.db from before roles existed is upgraded. Accounts that never used Google become
    guests, and Google-linked ones students."""
    path = tmp_path / "users.db"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE COLLATE NOCASE,"
        " name TEXT NOT NULL, password_hash TEXT NOT NULL, google_sub TEXT UNIQUE, picture TEXT,"
        " default_password INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    old.execute("INSERT INTO users (email, name, password_hash) VALUES ('old@example.com', 'Old', 'x')")
    old.execute(
        "INSERT INTO users (email, name, password_hash, google_sub) VALUES ('ub@ub.edu.ph', 'Ub', 'x', 'g-1')"
    )
    old.commit()
    old.close()

    store = UserStore(path, "12345678")
    assert store.get_by_email("old@example.com").role == "guest"
    assert store.get_by_email("ub@ub.edu.ph").role == "student"
    # The upgrade runs once: a role set afterwards stays, even across restarts.
    store.set_role("old@example.com", "student")
    assert UserStore(path, "12345678").get_by_email("old@example.com").role == "student"


def test_require_role_lets_only_those_roles_through():
    guarded = FastAPI()

    @guarded.get("/admin-only")
    def admin_only(user=Depends(auth.require_role("admin"))):
        return {"name": user.name}

    @guarded.get("/staff")
    def staff(user=Depends(auth.require_role("department", "admin"))):
        return {"office": user.office_id}

    c = TestClient(guarded)
    student, admin = headers_for(), headers_for("admin")
    office = headers_for("department", "registrar")

    assert c.get("/admin-only").status_code == 401
    assert c.get("/admin-only", headers=student).status_code == 403
    assert c.get("/admin-only", headers=office).status_code == 403
    assert c.get("/admin-only", headers=admin).status_code == 200

    assert c.get("/staff", headers=student).status_code == 403
    assert c.get("/staff", headers=office).json() == {"office": "registrar"}
    assert c.get("/staff", headers=admin).status_code == 200


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_chat_needs_a_signed_in_account(path):
    assert client.post(path, json={"message": "Hello"}).status_code == 401
    assert client.post(path, json={"message": "Hello"}, headers={"Authorization": "Bearer 1.9999999999.forged"}).status_code == 401


def test_speak_needs_a_signed_in_account():
    assert client.post("/api/speak", json={"text": "hello"}).status_code == 401


def test_conversations_are_kept_per_account(monkeypatch):
    """Two students using the same session id must not share follow-up memory."""
    seen = []

    def fake_answer(message, session_id):
        seen.append(session_id)
        raise RuntimeError("stop here")

    monkeypatch.setattr(chat_router, "_ready", lambda: None)
    monkeypatch.setattr(engine, "answer", fake_answer)
    for headers in (headers_for(), headers_for()):
        client.post("/api/chat", json={"message": "Hi", "session_id": "same"}, headers=headers)
    assert len(seen) == 2 and seen[0] != seen[1]
    assert all(s.endswith(":same") for s in seen)


def test_set_role_command(capsys):
    email = new_email()
    auth.get_store().create(email, "Lu")

    assert set_role.main([email, "department", "guidance"]) == 0
    assert "Guidance Office" in capsys.readouterr().out
    assert auth.get_store().get_by_email(email).office_id == "guidance"

    assert set_role.main([email, "department", "no-such-office"]) == 1
    assert set_role.main([email, "admin", "guidance"]) == 1
    assert set_role.main([new_email(), "admin"]) == 1
    assert set_role.main([email, "owner"]) == 1
    assert auth.get_store().get_by_email(email).role == "department"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/chat", {"message": "Hello"}),
        ("post", "/api/chat/stream", {"message": "Hello"}),
        ("post", "/api/speak", {"text": "Hello"}),
        ("post", "/api/tickets", {"question": "Hi?", "office_id": "registrar"}),
        ("get", "/api/tickets", None),
        ("post", "/api/documents/check", None),
    ],
)
@pytest.mark.parametrize("role", ["admin", "department"])
def test_staff_and_admins_dont_use_the_assistant(method, path, body, role):
    headers = headers_for(role, "registrar" if role == "department" else None)
    response = getattr(client, method)(path, headers=headers, **({"json": body} if body else {}))
    assert response.status_code == 403
