"""The department dashboard: office staff list and answer their own office's questions."""

from accounts import headers_for
from fastapi.testclient import TestClient
from test_tickets import ask, outbox, read_email, sign_up

from app.main import app

client = TestClient(app)


def office_tickets(headers):
    return client.get("/api/department/tickets", headers=headers)


def answer(headers, ref, text="Yes, ask at window 3.", answered_by=""):
    return client.post(
        f"/api/department/tickets/{ref}/answer",
        json={"answer": text, "answered_by": answered_by},
        headers=headers,
    )


def test_staff_see_only_their_own_offices_questions():
    student, _ = sign_up()
    to_registrar = ask(student, "Can I get my TOR early?", "registrar").json()["ref"]
    to_accounting = ask(student, "When is the tuition due?", "accounting").json()["ref"]

    body = office_tickets(headers_for("department", "registrar")).json()
    refs = [t["ref"] for t in body]
    assert to_registrar in refs and to_accounting not in refs
    mine = next(t for t in body if t["ref"] == to_registrar)
    assert mine["student_name"] == "Tess" and mine["status"] == "open"


def test_only_department_staff_open_the_dashboard():
    assert office_tickets({}).status_code == 401
    assert office_tickets(sign_up()[0]).status_code == 403
    assert office_tickets(headers_for("admin")).status_code == 403


def test_staff_answer_and_the_student_sees_it():
    student, _ = sign_up()
    ref = ask(student).json()["ref"]
    staff = headers_for("department", "registrar")

    saved = answer(staff, ref, "  Yes, ask at window 3.  ")
    assert saved.status_code == 200
    assert saved.json()["status"] == "answered"
    assert saved.json()["answer"] == "Yes, ask at window 3."
    assert saved.json()["answered_by"] == "Test department"  # the staff member's name by default

    seen = client.get("/api/tickets", headers=student).json()[0]
    assert seen["ref"] == ref and seen["answer"] == "Yes, ask at window 3."


def test_answered_by_can_be_named():
    ref = ask(sign_up()[0]).json()["ref"]
    body = answer(headers_for("department", "registrar"), ref, answered_by="Ms. Reyes").json()
    assert body["answered_by"] == "Ms. Reyes"


def test_staff_cannot_answer_another_offices_question():
    ref = ask(sign_up()[0], office="accounting").json()["ref"]
    assert answer(headers_for("department", "registrar"), ref).status_code == 404
    assert answer(headers_for("department", "registrar"), "UBT-999999").status_code == 404
    assert answer(headers_for("department", "registrar"), "nonsense").status_code == 404


def test_answer_must_not_be_blank():
    ref = ask(sign_up()[0]).json()["ref"]
    assert answer(headers_for("department", "registrar"), ref, "   ").status_code == 422


def test_verified_students_are_emailed_when_answered_from_the_dashboard():
    student, student_email = sign_up(google_linked=True)
    ref = ask(student).json()["ref"]
    before = len(outbox())
    answer(headers_for("department", "registrar"), ref)
    new = outbox()[before:]
    assert len(new) == 1 and student_email in read_email(new[0])


def test_staff_accounts_report_their_office():
    me = client.get("/api/auth/me", headers=headers_for("department", "registrar")).json()
    assert me["role"] == "department"
    assert me["office_id"] == "registrar" and me["office_name"] == "Registrar's Office"
