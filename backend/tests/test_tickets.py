import re
import uuid
from email import message_from_bytes, policy

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.routers import auth

client = TestClient(app)


def sign_up(google_linked=False):
    """A fresh student. Google-linked students have a verified email address."""
    email = f"t-{uuid.uuid4().hex[:8]}@example.com"
    if google_linked:
        user, _ = auth.get_store().sign_in_with_google(uuid.uuid4().hex, email, "Gina", None)
        token = auth._session(user).token
    else:
        token = client.post("/api/auth/signup", json={"name": "Tess", "email": email}).json()["token"]
    return {"Authorization": f"Bearer {token}"}, email


def outbox():
    folder = get_settings().mail_outbox_dir
    return sorted(folder.glob("*.eml")) if folder.exists() else []


def ask(headers, question="Can I get a copy of my grades early?", office="registrar"):
    return client.post("/api/tickets", json={"question": question, "office_id": office}, headers=headers)


def read_email(path):
    """Headers and decoded body, the way a mail program shows it."""
    message = message_from_bytes(path.read_bytes(), policy=policy.default)
    headers = "".join(f"{key}: {value}\n" for key, value in message.items())
    return headers + "\n" + message.get_content()


def answer_link_from(email_file):
    text = read_email(email_file)
    match = re.search(r"/answer/(UBT-\d+)\?t=(\S+)", text)
    return match.group(1), match.group(2)


def test_offices_are_listed_with_a_suggestion():
    body = client.get("/api/offices", params={"question": "When is the tuition payment due?"}).json()
    assert {"id": "accounting", "name": "Accounting / Cashier"} in body["offices"]
    assert body["suggested"] == "accounting"


def test_asking_an_office_needs_sign_in():
    assert ask({}).status_code == 401


def test_ticket_emails_the_office_with_a_private_answer_link():
    headers, student_email = sign_up()
    before = len(outbox())

    response = ask(headers)
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["ref"].startswith("UBT-") and ticket["status"] == "open"

    emails = outbox()
    assert len(emails) == before + 1
    text = read_email(emails[-1])
    assert "To: registrar@example.com" in text
    assert ticket["ref"] in text
    assert student_email not in text  # the office never sees the student's address


def test_office_answers_through_the_link_and_the_student_sees_it():
    headers, _ = sign_up()
    ref = ask(headers).json()["ref"]
    link_ref, token = answer_link_from(outbox()[-1])
    assert link_ref == ref

    page = client.get(f"/answer/{ref}", params={"t": token})
    assert page.status_code == 200 and "Can I get a copy of my grades early?" in page.text

    saved = client.post(f"/answer/{ref}", data={"t": token, "answer": "Yes, request it at window 3.", "answered_by": "Ms. Reyes"})
    assert saved.status_code == 200 and "Thank you" in saved.text

    mine = client.get("/api/tickets", headers=headers).json()
    assert mine[0]["ref"] == ref
    assert mine[0]["status"] == "answered"
    assert mine[0]["answer"] == "Yes, request it at window 3."
    assert mine[0]["answered_by"] == "Ms. Reyes"


@pytest.mark.parametrize("token", ["", "wrong-token"])
def test_answer_link_needs_the_right_token(token):
    headers, _ = sign_up()
    ref = ask(headers).json()["ref"]
    assert client.get(f"/answer/{ref}", params={"t": token}).status_code == 404
    assert client.post(f"/answer/{ref}", data={"t": token, "answer": "spam"}).status_code == 404


def test_only_verified_students_get_an_email_when_answered():
    for google_linked, expect_email in [(False, False), (True, True)]:
        headers, student_email = sign_up(google_linked=google_linked)
        ref = ask(headers).json()["ref"]
        _, token = answer_link_from(outbox()[-1])
        before = len(outbox())
        client.post(f"/answer/{ref}", data={"t": token, "answer": "Done."})
        new = outbox()[before:]
        assert any(student_email in read_email(f) for f in new) is expect_email


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


def test_failed_email_does_not_leave_an_orphan_ticket(monkeypatch):
    from app import mail

    def broken(*args, **kwargs):
        raise mail.MailError("SMTP is down")

    monkeypatch.setattr(mail, "send", broken)
    headers, _ = sign_up()
    assert ask(headers).status_code == 502
    assert client.get("/api/tickets", headers=headers).json() == []


def test_unanswerable_question_offers_an_office(index):
    headers, _ = sign_up()
    body = client.post("/api/chat", json={"message": "What is the capital of France?"}, headers=headers).json()
    assert body["can_reroute"] is True
    greeting = client.post("/api/chat", json={"message": "Hello!"}, headers=headers).json()
    assert greeting["can_reroute"] is False
