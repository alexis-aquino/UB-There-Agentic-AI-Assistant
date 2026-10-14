"""The admin dashboard: inquiry report, office workload and account roles."""

import tempfile
from pathlib import Path

import pytest
from accounts import headers_for
from fastapi.testclient import TestClient
from test_tickets import ask, sign_up

from app.brain.memory import Memory
from app.main import app
from app.routers import admin, auth

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_headers():
    return headers_for("admin")


def me(headers):
    return client.get("/api/auth/me", headers=headers).json()


@pytest.mark.parametrize("path", ["/api/admin/report", "/api/admin/users"])
def test_only_admins_open_the_dashboard(path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers=sign_up()[0]).status_code == 403
    assert client.get(path, headers=headers_for("department", "registrar")).status_code == 403


def test_report_counts_questions_gaps_and_sources(admin_headers):
    log = admin.get_query_log()
    before = client.get("/api/admin/report", headers=admin_headers).json()["inquiries"]
    log.log_inquiry("s", "Can I dye my hair?", True, 0.8, "studenthandbook.pdf, p. 40")
    log.log_inquiry("s", "Where is the canteen?", False, 0.0, None)
    log.log_inquiry("s", "where is the canteen? ", False, 0.0, None)

    after = client.get("/api/admin/report", headers=admin_headers).json()["inquiries"]
    assert after["asked"] == before["asked"] + 3
    assert after["answered"] == before["answered"] + 1
    canteen = next(q for q in after["unanswered"] if q["question"].lower().strip() == "where is the canteen?")
    assert canteen["count"] == 2  # the same question, asked twice, listed once
    assert any(s["source"] == "studenthandbook.pdf, p. 40" for s in after["top_sources"])
    assert len(after["per_day"]) == 14 and after["per_day"][-1]["asked"] >= 3


def test_report_fills_quiet_days():
    log = Memory(Path(tempfile.mkdtemp()) / "log.db")
    report = log.inquiry_report(days=7)
    assert report["asked"] == 0 and report["unanswered"] == []
    assert [d["asked"] for d in report["per_day"]] == [0] * 7
    days = [d["day"] for d in report["per_day"]]
    assert days == sorted(days) and len(set(days)) == 7


def test_report_rejects_silly_ranges(admin_headers):
    assert client.get("/api/admin/report?days=0", headers=admin_headers).status_code == 422
    assert client.get("/api/admin/report?days=500", headers=admin_headers).status_code == 422


def test_report_shows_each_offices_workload(admin_headers):
    ask(sign_up()[0], office="guidance")
    offices = client.get("/api/admin/report", headers=admin_headers).json()["offices"]
    guidance = next(o for o in offices if o["id"] == "guidance")
    assert guidance["name"] == "Guidance Office" and guidance["open"] >= 1


def test_admin_assigns_roles(admin_headers):
    student, _ = sign_up()
    user_id = me(student)["id"]

    made_staff = client.put(
        f"/api/admin/users/{user_id}/role",
        json={"role": "department", "office_id": "scholarships"},
        headers=admin_headers,
    ).json()
    assert made_staff["role"] == "department" and made_staff["office_name"] == "Scholarship Office"
    assert client.get("/api/department/tickets", headers=student).status_code == 200  # same token

    back = client.put(
        f"/api/admin/users/{user_id}/role", json={"role": "student", "office_id": "scholarships"}, headers=admin_headers
    ).json()
    assert back["role"] == "student" and back["office_id"] is None


@pytest.mark.parametrize(
    "payload, status",
    [
        ({"role": "department"}, 400),  # needs an office
        ({"role": "department", "office_id": "nowhere"}, 400),
        ({"role": "superuser"}, 422),
    ],
)
def test_role_changes_are_checked(admin_headers, payload, status):
    user_id = me(sign_up()[0])["id"]
    assert client.put(f"/api/admin/users/{user_id}/role", json=payload, headers=admin_headers).status_code == status


def test_unknown_account_and_self_demotion_are_refused(admin_headers):
    assert (
        client.put("/api/admin/users/999999/role", json={"role": "student"}, headers=admin_headers).status_code == 404
    )
    own_id = me(admin_headers)["id"]
    refused = client.put(f"/api/admin/users/{own_id}/role", json={"role": "student"}, headers=admin_headers)
    assert refused.status_code == 400
    assert auth.get_store().get(own_id).role == "admin"


def test_users_are_listed_with_roles(admin_headers):
    staff = me(headers_for("department", "registrar"))
    listed = client.get("/api/admin/users", headers=admin_headers).json()
    row = next(u for u in listed if u["id"] == staff["id"])
    assert row["role"] == "department" and row["office_id"] == "registrar"


def test_handbook_questions_from_the_chat_are_logged(index, admin_headers):
    before = client.get("/api/admin/report", headers=admin_headers).json()["inquiries"]
    student = headers_for()
    client.post("/api/chat", json={"message": "Hello!", "session_id": "log"}, headers=student)
    client.post("/api/chat", json={"message": "What is the capital of France?", "session_id": "log"}, headers=student)

    after = client.get("/api/admin/report", headers=admin_headers).json()["inquiries"]
    assert after["asked"] == before["asked"] + 1  # small talk isn't a handbook question
    assert any(q["question"] == "What is the capital of France?" for q in after["unanswered"])
