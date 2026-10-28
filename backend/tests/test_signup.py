import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.departments import load_departments
from app.config import get_settings
from app.main import app
from tests.test_admin import ADMIN

client = TestClient(app)
DEPT = load_departments()[0]  # whatever backend/departments.json lists first


@pytest.fixture
def no_google(monkeypatch):
    """Google sign-in off: UB addresses can sign up with a password (the tests turn it on)."""
    monkeypatch.setattr(get_settings(), "google_client_id", "")


def signup(account_type, email, department=None):
    body = {"name": "Tess", "email": email, "account_type": account_type}
    if department:
        body["department"] = department
    return client.post("/api/auth/signup", json=body)


def ub():
    return f"t-{uuid.uuid4().hex[:8]}@ub.edu.ph"


def test_departments_are_in_the_config():
    assert DEPT in client.get("/api/auth/config").json()["departments"]


def test_a_student_signs_up_with_a_department(no_google):
    user = signup("student", ub(), DEPT).json()["user"]
    assert user["account_type"] == "student" and user["department"] == DEPT and not user["guest"]


def test_a_guest_has_no_department():
    user = signup("guest", f"g-{uuid.uuid4().hex[:8]}@example.com", DEPT).json()["user"]
    assert user["account_type"] == "guest" and user["department"] is None and user["guest"]


@pytest.mark.parametrize(
    "account_type, email, department, message",
    [
        ("student", "someone@example.com", DEPT, "UB Mail"),  # students need a UB address
        ("department", "office@example.com", DEPT, "UB Mail"),
        ("student", None, None, "department"),  # and a department
        ("student", None, "College of Magic", "department"),  # from the list
        ("guest", None, None, "student or department"),  # UB addresses aren't guests
    ],
)
def test_signup_rules(no_google, account_type, email, department, message):
    response = signup(account_type, email or ub(), department)
    assert response.status_code == 400 and message in response.json()["detail"]


def test_with_google_on_ub_addresses_must_use_google():
    response = signup("student", ub(), DEPT)
    assert response.status_code == 400 and "Google" in response.json()["detail"]


def test_a_department_waits_for_an_admin_to_approve_it(no_google):
    email = ub()
    user = signup("department", email, DEPT).json()["user"]
    assert user["account_type"] == "department" and user["approved"] is False

    listed = {a["email"]: a for a in client.get("/api/admin/accounts", headers=ADMIN).json()["accounts"]}[email]
    assert listed["role"] == "department" and listed["pending"] is True and listed["department"] == DEPT

    after = client.post("/api/admin/accounts/approve", json={"ids": [listed["id"]]}, headers=ADMIN).json()
    assert {a["email"]: a for a in after["accounts"]}[email]["pending"] is False

    token = client.post("/api/auth/login", json={"email": email, "password": "12345678"}).json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["approved"] is True


def test_only_department_accounts_can_be_approved(no_google):
    email = ub()
    student = signup("student", email, DEPT).json()["user"]
    client.post("/api/admin/accounts/approve", json={"ids": [student["id"]]}, headers=ADMIN)
    listed = {a["email"]: a for a in client.get("/api/admin/accounts", headers=ADMIN).json()["accounts"]}[email]
    assert listed["role"] == "student" and listed["pending"] is False
