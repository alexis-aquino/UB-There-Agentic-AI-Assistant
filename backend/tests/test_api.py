import json

import pytest
from fastapi.testclient import TestClient

from app.brain.llm import ModelUnavailableError
from app.main import app
from app.routers import chat as chat_router
from accounts import headers_for

client = TestClient(app, headers=headers_for())


def chat(message, session_id="test"):
    return client.post("/api/chat", json={"message": message, "session_id": session_id})


def test_health_reports_brain_and_voice():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert "ready" in body["brain"]
    assert body["voice"]["provider"] == "off"


@pytest.mark.parametrize(
    "payload",
    [{"message": ""}, {"message": "x" * 2001}, {}, {"message": "hi", "session_id": "s" * 65}],
)
def test_chat_rejects_invalid_input(payload):
    assert client.post("/api/chat", json=payload).status_code == 422


def test_greeting_skips_retrieval(index):
    body = chat("Hello!").json()
    assert body["intent"] == "greeting"
    assert body["sources"] == []


def test_answer_has_sources_from_the_handbook(index):
    body = chat("Can male students wear earrings?", "a").json()
    assert body["sources"] and all(s.startswith("studenthandbook.pdf") for s in body["sources"])
    # The earrings rules are on p.99 and p.146 (the offline test model only quotes excerpts).
    assert any(s.endswith(("p.99", "p.146")) for s in body["sources"])
    assert body["can_reroute"] is False


def test_refusal_has_no_sources_and_offers_an_office(index):
    body = chat("What is the capital of France?", "refuse").json()
    assert body["sources"] == []
    assert "couldn't find" in body["reply"]
    assert body["can_reroute"] is True


def test_follow_up_is_searched_with_the_previous_question(index):
    chat("Can male students wear earrings?", "follow")
    body = chat("What about female students?", "follow").json()
    assert any("Follow-up" in line for line in body["trace"])
    assert body["sources"]


def test_stream_sends_the_reply_in_pieces_then_a_summary(index):
    response = client.post("/api/chat/stream", json={"message": "What is the grading system?", "session_id": "stream"})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    deltas = [e for e in events if e["type"] == "delta"]
    done = events[-1]
    assert len(deltas) > 1, "the reply should arrive in several pieces"
    assert done["type"] == "done"
    assert "".join(e["text"] for e in deltas).strip() == done["reply"]


def test_chat_says_503_when_the_model_is_not_running(index, monkeypatch):
    def down():
        raise ModelUnavailableError("The AI model isn't running.")

    monkeypatch.setattr(chat_router, "check_models", down)
    assert chat("Hello").status_code == 503
    stream = client.post("/api/chat/stream", json={"message": "Hello"})
    assert stream.status_code == 503
    assert "isn't running" in stream.json()["detail"]


def test_speak_returns_503_when_voice_is_off():
    """503 is the frontend's cue to fall back to browser speech."""
    assert client.post("/api/speak", json={"text": "hello"}).status_code == 503


def test_speak_rejects_empty_text():
    assert client.post("/api/speak", json={"text": ""}).status_code == 422


def test_cors_allows_the_frontend():
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5273",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5273"


def test_voices_lists_ai_voices_with_one_default():
    body = client.get("/api/voice/voices").json()
    ids = [voice["id"] for voice in body["voices"]]
    assert "en_US-lessac-medium" in ids and "en_US-amy-medium" in ids
    assert sum(voice["default"] for voice in body["voices"]) == 1


def test_speak_rejects_unknown_voice(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "voice_provider", "piper")
    response = client.post("/api/speak", json={"text": "hello", "voice": "not-a-voice"})
    assert response.status_code == 400
