import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.departments import load_departments
from app.config import get_settings
from app.main import app
from app.routers import auth
from tests.test_admin import ADMIN

client = TestClient(app)
REGISTRAR = "Registrar's Office"
COLLEGE = load_departments()[0]


def sign_up(department=None):
    """A fresh student, in `department` if given (a guest otherwise)."""
    if department:
        user = auth.get_store().create(
            f"s-{uuid.uuid4().hex[:8]}@ub.edu.ph", "Sam", account_type="student", department=department
        )
    else:
        user = auth.get_store().create(f"t-{uuid.uuid4().hex[:8]}@example.com", "Tess", account_type="guest")
    return {"Authorization": f"Bearer {auth._session(user).token}"}, user


def staff(office):
    """An approved University department account for an office or college."""
    store = auth.get_store()
    user = store.create(f"o-{uuid.uuid4().hex[:8]}@ub.edu.ph", "Ms. Reyes", account_type="department", department=office)
    store.approve([user.id], "Test")
    return {"Authorization": f"Bearer {auth._session(store.get(user.id)).token}"}


def ask(headers, question="Can I get a copy of my grades early?", office="registrar"):
    return client.post("/api/tickets", json={"question": question, "office_id": office}, headers=headers)


def inbox(headers):
    return client.get("/api/admin/tickets", headers=headers)


def reply(headers, ref, text="Yes, request it at window 3."):
    return client.post(f"/api/admin/tickets/{ref}/answer", json={"answer": text}, headers=headers)


def test_offices_and_colleges_are_listed_with_a_suggestion():
    body = client.get("/api/offices", params={"question": "When is the tuition payment due?"}).json()
    assert {"id": "accounting", "name": "Accounting / Cashier", "kind": "office"} in body["offices"]
    assert {"id": COLLEGE, "name": COLLEGE, "kind": "department"} in body["offices"]
    assert body["suggested"] == "accounting"


def test_a_students_own_college_is_suggested_when_no_office_fits():
    headers, _ = sign_up(COLLEGE)
    question = {"question": "Who is my thesis adviser?"}
    assert client.get("/api/offices", params=question, headers=headers).json()["suggested"] == COLLEGE
    assert client.get("/api/offices", params=question).json()["suggested"] == "registrar"


def test_asking_an_office_needs_sign_in():
    assert ask({}).status_code == 401


def test_the_office_answers_in_the_dashboard_and_the_student_sees_it():
    headers, student = sign_up(COLLEGE)
    registrar = staff(REGISTRAR)
    response = ask(headers)
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["ref"].startswith("UBT-") and ticket["status"] == "open"

    waiting = next(t for t in inbox(registrar).json() if t["ref"] == ticket["ref"])
    assert waiting["student_name"] == "Sam" and waiting["student_department"] == COLLEGE
    assert student.email not in str(waiting)  # the office never sees the student's address

    answered = reply(registrar, ticket["ref"]).json()
    assert answered["status"] == "answered" and answered["answered_by"] == "Ms. Reyes"

    mine = client.get("/api/tickets", headers=headers).json()
    assert mine[0]["ref"] == ticket["ref"]
    assert mine[0]["status"] == "answered"
    assert mine[0]["answer"] == "Yes, request it at window 3."


def test_a_college_receives_the_questions_sent_to_it():
    headers, _ = sign_up(COLLEGE)
    college = staff(COLLEGE)
    ref = ask(headers, "Who is my thesis adviser?", office=COLLEGE).json()["ref"]
    assert ref in [t["ref"] for t in inbox(college).json()]
    assert reply(college, ref).status_code == 200


def test_offices_only_see_and_answer_their_own_questions():
    headers, _ = sign_up()
    ref = ask(headers).json()["ref"]
    guidance = staff("Guidance Office")
    assert ref not in [t["ref"] for t in inbox(guidance).json()]
    assert reply(guidance, ref).status_code == 404


def test_an_offices_inquiry_report_is_the_questions_sent_to_it():
    from tests.test_admin import log

    headers, student = sign_up(COLLEGE)
    sent, kept = log("Can I get my grades early?", user_id=student.id, answered=False), log(user_id=student.id)
    body = {"question": "Can I get my grades early?", "office_id": "registrar", "inquiry_id": sent}
    client.post("/api/tickets", json=body, headers=headers)
    registrar, guidance = staff(REGISTRAR), staff("Guidance Office")

    seen = {r["id"]: r for r in client.get("/api/admin/inquiries", headers=registrar).json()["inquiries"]}
    assert sent in seen and kept not in seen and seen[sent]["status"] == "pending"
    assert sent not in {r["id"] for r in client.get("/api/admin/inquiries", headers=guidance).json()["inquiries"]}
    flag = f"/api/admin/inquiries/{sent}/flag"
    assert client.put(flag, json={"flagged": True}, headers=registrar).status_code == 200
    assert client.put(flag, json={"flagged": True}, headers=guidance).status_code == 404


def test_the_admin_sees_every_question_and_can_answer_any():
    headers, _ = sign_up()
    ref = ask(headers, office="guidance").json()["ref"]
    assert ref in [t["ref"] for t in inbox(ADMIN).json()]
    assert reply(ADMIN, ref).status_code == 200


def test_a_question_is_answered_once():
    headers, _ = sign_up()
    registrar = staff(REGISTRAR)
    ref = ask(headers).json()["ref"]
    assert reply(registrar, ref).status_code == 200
    assert reply(registrar, ref, "Changed my mind").status_code == 409
    assert reply(registrar, ask(headers).json()["ref"], "   ").status_code == 422


def test_a_deleted_students_question_is_closed():
    headers, student = sign_up()
    registrar = staff(REGISTRAR)
    ref = ask(headers).json()["ref"]
    auth.get_store().delete([student.id])
    assert next(t for t in inbox(registrar).json() if t["ref"] == ref)["closed"] is True
    assert reply(registrar, ref).status_code == 410


def test_students_and_unapproved_staff_have_no_inbox():
    student, _ = sign_up(COLLEGE)
    store = auth.get_store()
    pending = store.create(f"p-{uuid.uuid4().hex[:8]}@ub.edu.ph", "New", account_type="department", department=REGISTRAR)
    for headers in (student, {"Authorization": f"Bearer {auth._session(pending).token}"}):
        assert inbox(headers).status_code == 403


def test_office_staff_sign_up_for_their_office_but_students_cannot(monkeypatch):
    def signup(kind):
        email = f"{kind}-{uuid.uuid4().hex[:8]}@ub.edu.ph"
        body = {"name": "X", "email": email, "account_type": kind, "department": REGISTRAR}
        return client.post("/api/auth/signup", json=body)

    monkeypatch.setattr(get_settings(), "google_client_id", "")  # UB addresses may use the form
    assert signup("department").status_code == 201
    assert signup("student").status_code == 400
    assert REGISTRAR in client.get("/api/auth/config").json()["offices"]


def test_an_office_typed_in_under_other_receives_questions_once_approved(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    name = f"University Library {uuid.uuid4().hex[:4]}"

    def signup(kind, department=name, unit_kind="office"):
        email = f"{kind}-{uuid.uuid4().hex[:8]}@ub.edu.ph"
        body = {"name": "X", "email": email, "account_type": kind, "department": department, "unit_kind": unit_kind}
        return client.post("/api/auth/signup", json=body)

    assert signup("student").status_code == 400  # students choose a listed college
    assert signup("department", "   ").status_code == 400
    assert signup("department", unit_kind=None).status_code == 400  # department or office?
    created = signup("department", f"  {name} ")
    assert created.status_code == 201 and created.json()["user"]["department"] == name

    listed = lambda: {o["name"]: o["kind"] for o in client.get("/api/offices").json()["offices"]}  # noqa: E731
    assert name not in listed()  # not until an administrator approves it
    auth.get_store().approve([created.json()["user"]["id"]], "Test")
    assert listed()[name] == "office" and name in client.get("/api/auth/config").json()["offices"]

    headers, _ = sign_up()
    ref = ask(headers, "Can I borrow books over the break?", office=name).json()["ref"]
    library = {"Authorization": f"Bearer {created.json()['token']}"}
    assert ref in [t["ref"] for t in inbox(library).json()]
    assert reply(library, ref).status_code == 200

    # A second staff member picks it from the list: it stays an office without being asked again.
    assert signup("department", unit_kind=None).status_code == 201
    staff_tags = {
        a["department"]: a["unitKind"]
        for a in client.get("/api/admin/accounts", headers=ADMIN).json()["accounts"]
        if a["role"] == "department"
    }
    assert staff_tags[name] == "office" and staff_tags[REGISTRAR] == "office" and staff_tags[COLLEGE] == "department"


def test_a_department_typed_in_under_other_gets_students_once_approved(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    name = f"Graduate School {uuid.uuid4().hex[:4]}"

    def signup(kind, unit_kind=None):
        email = f"{kind}-{uuid.uuid4().hex[:8]}@ub.edu.ph"
        body = {"name": "X", "email": email, "account_type": kind, "department": name, "unit_kind": unit_kind}
        return client.post("/api/auth/signup", json=body)

    created = signup("department", "department")
    assert signup("student").status_code == 400  # not until it's approved
    auth.get_store().approve([created.json()["user"]["id"]], "Test")

    config = client.get("/api/auth/config").json()
    assert name in config["departments"] and name not in config["offices"]
    student = signup("student")
    assert student.status_code == 201
    listed = {o["name"]: o["kind"] for o in client.get("/api/offices").json()["offices"]}
    assert listed[name] == "department"

    # Its dashboard is a department's: its own students' questions.
    from tests.test_admin import log

    asked = log(user_id=student.json()["user"]["id"])
    dept = {"Authorization": f"Bearer {created.json()['token']}"}
    assert asked in {r["id"] for r in client.get("/api/admin/inquiries", headers=dept).json()["inquiries"]}


def test_students_only_see_their_own_tickets():
    mine, _ = sign_up()
    theirs, _ = sign_up()
    ref = ask(theirs).json()["ref"]
    assert ref not in [t["ref"] for t in client.get("/api/tickets", headers=mine).json()]


def test_daily_limit_protects_offices(monkeypatch):
    monkeypatch.setattr(get_settings(), "tickets_per_day", 2)
    headers, _ = sign_up()
    assert ask(headers).status_code == 201
    assert ask(headers).status_code == 201
    assert ask(headers).status_code == 429


@pytest.mark.parametrize("payload", [{"question": "   ", "office_id": "registrar"}, {"question": "Hi?", "office_id": "nope"}])
def test_ticket_input_is_checked(payload):
    headers, _ = sign_up()
    assert client.post("/api/tickets", json=payload, headers=headers).status_code in (400, 422)


@pytest.mark.parametrize(
    ("reply", "not_found"),
    [
        # Said by llama3.2 when the handbook had nothing; each must offer "Ask an office".
        ("The deadline to pay the tuition installment for this semester isn't really mentioned in the handbook, "
         "but it does say that if you pay in full you get a discount.", True),
        ("The Wi-Fi password isn't explicitly mentioned in the handbook.", True),
        ("I couldn't find that in the handbook.", True),
        ("The handbook doesn't actually say who your thesis adviser is.", True),
        ("There's no information about late applications in the handbook.", True),
        # Real answers that happen to contain "not" or "don't".
        ("Lab fees are not refundable once classes start.", False),
        ("If you don't pay on time, a penalty of 5% applies.", False),
        ("A student who did not take the exam must file a request within a week.", False),
    ],
)
def test_a_reply_saying_the_handbook_lacks_it_offers_an_office(reply, not_found):
    from app.brain.engine import NOT_FOUND_RE

    assert bool(NOT_FOUND_RE.search(reply)) is not_found


def test_unanswerable_question_offers_an_office(index):
    body = client.post("/api/chat", json={"message": "What is the capital of France?"}).json()
    assert body["can_reroute"] is True
    greeting = client.post("/api/chat", json={"message": "Hello!"}).json()
    assert greeting["can_reroute"] is False
