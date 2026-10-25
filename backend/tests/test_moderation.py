import pytest
from fastapi.testclient import TestClient

from app.brain.moderation import OFF_TOPIC, OFFENSIVE, flag_reason
from app.main import app
from tests.test_admin import ADMIN

client = TestClient(app)


@pytest.mark.parametrize(
    "question",
    ["You are a useless stupid bot", "you are so stupid", "bobo mo naman", "Tangina, sagutin mo na"],
)
def test_insults_are_offensive(question):
    assert flag_reason(question, handbook_matched=True) == OFFENSIVE


@pytest.mark.parametrize(
    "question",
    ["Who will win the NBA finals this year?", "Give me a recipe for chicken adobo", "Tell me a joke"],
)
def test_questions_about_other_things_are_off_topic(question):
    assert flag_reason(question, handbook_matched=False) == OFF_TOPIC


@pytest.mark.parametrize(
    "question, matched",
    [
        ("Can I bring my dog to class?", False),  # about school, just not in the handbook
        ("What are your hours?", False),
        ("Is it stupid to drop a subject?", True),  # a mild word, not aimed at anyone
        ("Can male students wear earrings?", True),
    ],
)
def test_real_questions_are_not_flagged(question, matched):
    assert flag_reason(question, handbook_matched=matched) is None


def test_the_assistant_flags_in_the_report_and_an_admin_can_clear_it(index):
    flagged = client.post("/api/chat", json={"message": "You are a useless stupid bot", "session_id": "mod"}).json()
    plain = client.post("/api/chat", json={"message": "Can male students wear earrings?", "session_id": "mod2"}).json()
    report = {r["id"]: r for r in client.get("/api/admin/inquiries", headers=ADMIN).json()["inquiries"]}

    assert report[flagged["inquiry_id"]]["flag"]["by"] == "Assistant · offensive language"
    assert report[flagged["inquiry_id"]]["flag"]["at"]
    assert report[plain["inquiry_id"]]["flag"] is None

    cleared = client.put(f"/api/admin/inquiries/{flagged['inquiry_id']}/flag", json={"flagged": False}, headers=ADMIN)
    assert cleared.json()["flag"] is None
