import uuid

from fastapi.testclient import TestClient

from app.brain.memory import get_memory
from app.brain.topics import topic_of
from app.main import app
from app.routers import auth
from tests.test_tickets import answer_link_from, outbox

client = TestClient(app)


def account(email, google=False):
    """Headers for an account made straight in the store (UB addresses can't use the sign-up form)."""
    store = auth.get_store()
    if google:
        user, _ = store.sign_in_with_google(uuid.uuid4().hex, email, "Boss", None)
    else:
        user = store.create(email, email.split("@")[0].title())
    return {"Authorization": f"Bearer {auth._session(user).token}"}, user


def unique(local, domain):
    return f"{local}-{uuid.uuid4().hex[:6]}@{domain}"


def log(question="How many units is an overload?", user_id=None, answered=True):
    return get_memory().log_inquiry(
        "s", user_id, question, topic_of(question), answered, "studenthandbook.pdf p.40" if answered else None,
        0.8 if answered else 0.0, "2026-10-01T08:00:00Z", "2026-10-01T08:00:02Z",
    )


ADMIN, ADMIN_USER = account("boss@ub.edu.ph", google=True)  # listed as Boss@ub.edu.ph: case doesn't matter


def test_only_listed_ub_accounts_are_admins():
    assert client.get("/api/auth/me", headers=ADMIN).json()["admin"] is True
    student, _ = account(unique("student", "ub.edu.ph"))
    assert client.get("/api/auth/me", headers=student).json()["admin"] is False
    # Listed, but not a UB address: a guest can never be an admin.
    outsider, _ = account("outsider@example.com")
    assert client.get("/api/auth/me", headers=outsider).json()["admin"] is False
    assert client.get("/api/admin/inquiries", headers=outsider).status_code == 403
    assert client.get("/api/admin/inquiries", headers=student).status_code == 403
    assert client.get("/api/admin/inquiries").status_code == 401


def test_inquiries_report_who_asked_and_the_status():
    student, user = account(unique("asker", "ub.edu.ph"))
    answered = log(user_id=user.id)
    rerouted = log("Can I bring my dog to class?", answered=False)

    body = client.get("/api/admin/inquiries", headers=ADMIN).json()
    assert "Enrollment" in body["topics"] and body["topics"][-1] == "Other"
    by_id = {r["id"]: r for r in body["inquiries"]}
    assert by_id[answered]["status"] == "answered"
    assert by_id[answered]["topic"] == "Enrollment"
    assert by_id[answered]["student"] == {"name": user.name, "email": user.email, "department": None}
    assert by_id[rerouted]["status"] == "rerouted"
    assert by_id[rerouted]["student"] is None
    assert by_id[rerouted]["ticket"] is None


def test_a_ticket_makes_its_question_pending():
    student, user = account(unique("ticket", "ub.edu.ph"))
    inquiry = log("Can I get my grades early?", user_id=user.id, answered=False)
    ticket = client.post(
        "/api/tickets",
        json={"question": "Can I get my grades early?", "office_id": "registrar", "inquiry_id": inquiry},
        headers=student,
    )
    assert ticket.status_code == 201
    record = next(r for r in client.get("/api/admin/inquiries", headers=ADMIN).json()["inquiries"] if r["id"] == inquiry)
    assert record["status"] == "pending"
    assert record["ticket"]["ref"] == ticket.json()["ref"]


def test_a_ticket_cannot_claim_someone_elses_question():
    _, owner = account(unique("owner", "ub.edu.ph"))
    other, _ = account(unique("other", "ub.edu.ph"))
    inquiry = log("Can I get my grades early?", user_id=owner.id, answered=False)
    client.post(
        "/api/tickets",
        json={"question": "Hijack", "office_id": "registrar", "inquiry_id": inquiry},
        headers=other,
    )
    record = next(r for r in client.get("/api/admin/inquiries", headers=ADMIN).json()["inquiries"] if r["id"] == inquiry)
    assert record["status"] == "rerouted"


def test_flagging_is_saved_and_can_be_cleared():
    inquiry = log("You are a useless bot", answered=False)
    flagged = client.put(f"/api/admin/inquiries/{inquiry}/flag", json={"flagged": True}, headers=ADMIN).json()
    assert flagged["flag"]["by"] == ADMIN_USER.name
    cleared = client.put(f"/api/admin/inquiries/{inquiry}/flag", json={"flagged": False}, headers=ADMIN).json()
    assert cleared["flag"] is None
    assert client.put("/api/admin/inquiries/999999/flag", json={"flagged": True}, headers=ADMIN).status_code == 404


def test_topics_follow_the_question():
    assert topic_of("When is the tuition payment due?") == "Tuition & fees"
    assert topic_of("Can male students wear earrings?") == "Uniform & dress code"
    assert topic_of("How do I replace a lost ID?") == "Student ID"
    assert topic_of("Who will win the NBA finals?") != "Enrollment"
    assert topic_of("Tell me a joke") == "Other"


def test_chat_logs_the_question_with_the_signed_in_student(index):
    student, user = account(unique("chat", "ub.edu.ph"))
    body = client.post(
        "/api/chat", json={"message": "Can male students wear earrings?", "session_id": "adm"}, headers=student
    ).json()
    assert body["inquiry_id"]
    record = next(r for r in client.get("/api/admin/inquiries", headers=ADMIN).json()["inquiries"] if r["id"] == body["inquiry_id"])
    assert record["student"]["email"] == user.email
    assert record["status"] == "answered"
    # Small talk isn't an inquiry.
    assert client.post("/api/chat", json={"message": "Hello!", "session_id": "adm"}).json()["inquiry_id"] is None


# ---------- accounts ----------


def accounts():
    return {a["email"]: a for a in client.get("/api/admin/accounts", headers=ADMIN).json()["accounts"]}


def test_accounts_list_real_users_with_their_activity():
    _, user = account(unique("active", "ub.edu.ph"))
    log(user_id=user.id)
    log("When is the tuition payment due?", user_id=user.id)
    listed = accounts()[user.email]
    assert listed["questions"] == 2
    assert listed["lastActiveAt"] and listed["createdAt"]
    assert listed["role"] == "student" and listed["disabled"] is None
    assert accounts()["boss@ub.edu.ph"]["role"] == "admin"
    assert accounts()["boss@ub.edu.ph"]["signIn"] == "UB mail"
    student, _ = account(unique("nosy", "ub.edu.ph"))
    assert client.get("/api/admin/accounts", headers=student).status_code == 403


def test_a_disabled_account_is_signed_out_and_cannot_sign_in():
    headers, user = account(unique("off", "example.com"))
    client.post("/api/admin/accounts/disable", json={"ids": [user.id]}, headers=ADMIN)
    assert accounts()[user.email]["disabled"]["by"] == ADMIN_USER.name
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    login = client.post("/api/auth/login", json={"email": user.email, "password": "12345678"})
    assert login.status_code == 403
    client.post("/api/admin/accounts/enable", json={"ids": [user.id]}, headers=ADMIN)
    assert client.post("/api/auth/login", json={"email": user.email, "password": "12345678"}).status_code == 200


def test_admins_cannot_disable_themselves():
    client.post("/api/admin/accounts/disable", json={"ids": [ADMIN_USER.id]}, headers=ADMIN)
    assert accounts()["boss@ub.edu.ph"]["disabled"] is None


def test_delete_waits_until_disabled_long_enough_and_keeps_the_history():
    headers, user = account(unique("gone", "ub.edu.ph"))
    answered = log(user_id=user.id)
    rerouted = log("Can I bring my dog to class?", user_id=user.id, answered=False)
    pending = log("Can I get my grades early?", user_id=user.id, answered=False)
    resolved = log("Can I shift courses mid-year?", user_id=user.id, answered=False)
    tickets = {}
    for inquiry in (pending, resolved):
        tickets[inquiry] = client.post(
            "/api/tickets",
            json={"question": "Office question", "office_id": "registrar", "inquiry_id": inquiry},
            headers=headers,
        ).json()["ref"]
        tickets[inquiry, "link"] = answer_link_from(outbox()[-1])
    ref, token = tickets[resolved, "link"]
    client.post(f"/answer/{ref}", data={"t": token, "answer": "Yes, file the form before week 3."})
    inquiry = answered
    client.post("/api/admin/accounts/disable", json={"ids": [user.id]}, headers=ADMIN)
    early = client.post("/api/admin/accounts/delete", json={"ids": [user.id]}, headers=ADMIN)
    assert early.status_code == 400 and user.email in accounts()

    # Pretend it was disabled 31 days ago.
    store = auth.get_store()
    with store._lock:
        store._connection.execute(
            "UPDATE users SET disabled_at = '2000-01-01T00:00:00Z' WHERE id = ?", (user.id,)
        )
        store._connection.commit()
    assert client.post("/api/admin/accounts/delete", json={"ids": [user.id]}, headers=ADMIN).status_code == 200
    assert user.email not in accounts()
    record = next(r for r in client.get("/api/admin/inquiries", headers=ADMIN).json()["inquiries"] if r["id"] == inquiry)
    assert record["student"] == {"name": user.name, "email": user.email, "department": None, "deleted": True}

    report = {r["id"]: r for r in client.get("/api/admin/inquiries", headers=ADMIN).json()["inquiries"]}
    # Settled questions keep their state; open ones are closed, with their tickets kept.
    assert report[answered]["status"] == "answered" and report[answered]["closedAt"] is None
    assert report[resolved]["status"] == "resolved"
    assert report[resolved]["ticket"]["answer"] == "Yes, file the form before week 3."
    assert report[rerouted]["status"] == "closed" and report[rerouted]["closedAt"]
    assert report[pending]["status"] == "closed" and report[pending]["ticket"]["ref"] == tickets[pending]
    assert all(report[i]["student"]["deleted"] for i in (answered, rerouted, pending, resolved))

    # The office can no longer answer: nobody would receive it.
    ref, token = tickets[pending, "link"]
    page = client.get(f"/answer/{ref}", params={"t": token})
    assert page.status_code == 410 and "account has been deleted" in page.text
    assert client.post(f"/answer/{ref}", data={"t": token, "answer": "Yes."}).status_code == 410
