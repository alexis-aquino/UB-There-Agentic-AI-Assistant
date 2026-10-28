import uuid

from fastapi.testclient import TestClient

from app.auth.departments import load_departments
from app.main import app
from app.routers import auth
from tests.test_admin import ADMIN, log

client = TestClient(app)
MINE, OTHER = load_departments()[0], load_departments()[1]


def make(kind, department=None, approved=False, domain="ub.edu.ph"):
    store = auth.get_store()
    user = store.create(f"{kind}-{uuid.uuid4().hex[:8]}@{domain}", kind.title(), account_type=kind, department=department)
    if approved:
        store.approve([user.id], "Test")
        user = store.get(user.id)
    return {"Authorization": f"Bearer {auth._session(user).token}"}, user


def ids(response):
    return {r["id"] for r in response.json()["inquiries"]}


def test_a_department_sees_only_its_own_students():
    dept, _ = make("department", MINE, approved=True)
    _, mine = make("student", MINE)
    _, other = make("student", OTHER)
    _, guest = make("guest", domain="example.com")
    q_mine, q_other, q_guest = log(user_id=mine.id), log(user_id=other.id), log(user_id=guest.id)

    seen = client.get("/api/admin/inquiries", headers=dept)
    assert seen.status_code == 200 and seen.json()["department"] == MINE
    assert q_mine in ids(seen) and not {q_other, q_guest} & ids(seen)
    record = next(r for r in seen.json()["inquiries"] if r["id"] == q_mine)
    assert record["student"]["department"] == MINE

    # The admin still sees everything.
    assert {q_mine, q_other, q_guest} <= ids(client.get("/api/admin/inquiries", headers=ADMIN))

    students = {a["email"] for a in client.get("/api/admin/accounts", headers=dept).json()["accounts"]}
    assert mine.email in students and other.email not in students and guest.email not in students


def test_a_department_cannot_manage_accounts():
    dept, _ = make("department", MINE, approved=True)
    _, student = make("student", MINE)
    for action in ("disable", "enable", "approve", "delete"):
        assert client.post(f"/api/admin/accounts/{action}", json={"ids": [student.id]}, headers=dept).status_code == 403


def test_a_department_flags_only_its_own_students_questions():
    dept, _ = make("department", MINE, approved=True)
    _, mine = make("student", MINE)
    _, other = make("student", OTHER)
    q_mine, q_other = log("You are a useless bot", user_id=mine.id), log("bobo", user_id=other.id)
    assert client.put(f"/api/admin/inquiries/{q_mine}/flag", json={"flagged": True}, headers=dept).json()["flag"]
    assert client.put(f"/api/admin/inquiries/{q_other}/flag", json={"flagged": True}, headers=dept).status_code == 404


def test_students_guests_and_unapproved_departments_get_no_dashboard():
    for headers in (make("student", MINE)[0], make("guest", domain="example.com")[0], make("department", MINE)[0]):
        assert client.get("/api/admin/inquiries", headers=headers).status_code == 403
        assert client.get("/api/admin/accounts", headers=headers).status_code == 403


def test_staff_edit_their_own_account_but_not_their_department():
    headers, user = make("department", MINE, approved=True)
    renamed = client.post(
        "/api/auth/profile", json={"name": "  CICT Dean's Office ", "department": OTHER}, headers=headers
    ).json()
    assert renamed["name"] == "CICT Dean's Office"
    assert renamed["department"] == MINE  # the department isn't theirs to change
    changed = client.post(
        "/api/auth/password", json={"current_password": "12345678", "new_password": "a-new-password"}, headers=headers
    )
    assert changed.status_code == 200 and changed.json()["default_password"] is False


def test_the_admin_edits_their_own_name_too():
    headers, _ = make("student", MINE)  # any account; the admin uses the same endpoint
    assert client.post("/api/auth/profile", json={"name": "New Name"}, headers=headers).json()["name"] == "New Name"
    assert client.post("/api/auth/profile", json={"name": "   "}, headers=headers).status_code == 422
    assert client.post("/api/auth/profile", json={"name": "x"}).status_code == 401
