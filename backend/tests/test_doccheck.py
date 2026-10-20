"""Document check: a student's photo, checked against the handbook's rules for that document.
The vision model is replaced by a stand-in; the handbook search is the real one."""

import pytest
from fastapi.testclient import TestClient
from test_tickets import sign_up

from app import doccheck
from app.main import app

client = TestClient(app)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def send(headers, image=PNG, note=""):
    return client.post(
        "/api/documents/check", files={"file": ("photo.png", image, "image/png")}, data={"note": note}, headers=headers
    )


@pytest.fixture
def vision(monkeypatch):
    """Set what the stand-in model "sees" and how it judges; records the prompts it got."""
    state = {
        "seen": {"is_document": True, "readable": True, "document_type": "school uniform", "search": "uniform policy"},
        "verdict": {
            "covered": True,
            "checks": [{"requirement": "Wear the prescribed uniform", "status": "met", "detail": "Shown."}],
            "summary": "Looks right.",
        },
        "prompts": [],
    }

    def fake(prompt, image, mime):
        state["prompts"].append(prompt)
        return state["seen"] if "Look at the photo" in prompt else state["verdict"]

    monkeypatch.setattr(doccheck, "vision_json", fake)
    return state


def test_a_document_the_handbook_covers_is_checked(index, vision):
    body = send(sign_up()[0]).json()
    assert body["status"] == "passed"
    assert body["checks"][0]["status"] == "met"
    assert body["citations"]  # the pages it was checked against
    assert "Handbook excerpts:" in vision["prompts"][1]  # judged against the handbook, not memory


def test_a_missing_requirement_needs_fixing(index, vision):
    vision["verdict"]["checks"].append({"requirement": "ID worn visibly", "status": "missing", "detail": "No ID."})
    body = send(sign_up()[0]).json()
    assert body["status"] == "needs_fixing"
    assert [c["status"] for c in body["checks"]] == ["met", "missing"]


def test_a_document_the_handbook_has_nothing_on_is_denied(index, vision):
    vision["seen"] = {"is_document": True, "readable": True, "document_type": "fishing licence", "search": "fishing licence"}
    body = send(sign_up()[0]).json()
    assert body["status"] == "denied" and body["checks"] == []
    assert len(vision["prompts"]) == 1  # never judged: there was nothing to judge it against


def test_denied_when_the_passages_found_state_no_requirements(index, vision):
    vision["verdict"] = {"covered": False, "checks": [], "summary": ""}
    assert send(sign_up()[0]).json()["status"] == "denied"


def test_an_unclear_photo_asks_for_a_retake(index, vision):
    vision["seen"]["readable"] = False
    body = send(sign_up()[0]).json()
    assert body["status"] == "unreadable" and len(vision["prompts"]) == 1


def test_the_students_note_reaches_the_model(index, vision):
    send(sign_up()[0], note="my excuse letter")
    assert '"my excuse letter"' in vision["prompts"][0]


def test_only_photos_are_accepted(index, vision):
    headers = sign_up()[0]
    assert send(headers, image=b"%PDF-1.7 not a photo").status_code == 400
    assert send(headers, image=b"").status_code == 400
    too_big = PNG + b"\x00" * doccheck.MAX_IMAGE_BYTES
    assert send(headers, image=too_big).status_code == 400
    assert vision["prompts"] == []


def test_needs_a_signed_in_account():
    assert send({}).status_code == 401


def test_each_student_has_a_daily_allowance(index, vision, monkeypatch):
    monkeypatch.setattr(doccheck.get_settings(), "doc_checks_per_day", 2)
    headers = sign_up()[0]
    assert send(headers).status_code == 200 and send(headers).status_code == 200
    refused = send(headers)
    assert refused.status_code == 400 and "up to 2 documents a day" in refused.json()["detail"]


def test_without_an_openai_key_it_says_so(index, monkeypatch):
    monkeypatch.setattr(doccheck.get_settings(), "openai_api_key", "")
    response = send(sign_up()[0])
    assert response.status_code == 503 and "OPENAI_API_KEY" in response.json()["detail"]


def test_each_check_is_logged_without_the_photo(index, vision):
    from app.brain import engine

    headers = sign_up()[0]
    vision["verdict"]["checks"].append({"requirement": "ID worn visibly", "status": "missing", "detail": ""})
    send(headers)
    me = client.get("/api/auth/me", headers=headers).json()["id"]
    logged = [e for e in engine.load().memory.query_log(1) if e["kind"] == "document" and e["user_id"] == me]
    assert logged and logged[0]["outcome"] == "needs_fixing" and logged[0]["missing"] == ["ID worn visibly"]
