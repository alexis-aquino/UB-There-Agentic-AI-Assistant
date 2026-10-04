"""Golden questions against the real student handbook index.

Each case pins the page the answer must cite and a phrase it must contain. When a change
to retrieval breaks one of these, the failure message shows what came back instead.
"""

import pytest

from app.brain.reflect import answer_question

ANSWERS = [
    ("What happens if a student is absent for too many hours?", "p.53", "20%"),
    ("What is the dress code for students?", "p.98", "uniform"),
    pytest.param(
        "What should students wear on campus?",
        "p.99",
        "appropriate attire",
        marks=pytest.mark.xfail(
            strict=True,
            reason="Known limit: the p.147 public-affection rule mentions campus, wearing and "
            "uniform in one sentence, so it outscores the attire guideline sentence by sentence.",
        ),
    ),
    ("What is the school uniform policy?", "p.97", "uniform"),
    ("Can I smoke on campus?", "p.145", "Smoking inside the campus"),
    ("What is the policy on hair color?", "p.99", "hair color"),
    ("Can male students wear earrings?", "p.99", "earrings"),
    ("What are the library hours?", "p.88", "Library Hours"),
    ("What is the grading system?", "p.54", "GRADING SYSTEM"),
    ("How do I shift to another course?", "p.59", "Shifting of courses"),
]

OFF_TOPIC = [
    "What is the capital of France?",
    "asdkjh qwpoeiru zxcmvn",
    "who won the world cup in 2018",
    "what is the weather today",
    # No tardiness rule is phrased that way; refusing beats citing a visa penalty.
    "What is the penalty for being tardy?",
]


@pytest.mark.parametrize("question,page,phrase", ANSWERS)
def test_answers_cite_the_right_passage(index, question, page, phrase):
    result = answer_question(index, question)
    assert result.grounded, result.trace
    assert any(source.endswith(page) for source in result.sources), (result.sources, result.text)
    assert phrase.lower() in result.text.lower(), result.text


@pytest.mark.parametrize("question", OFF_TOPIC)
def test_off_topic_questions_are_not_answered(index, question):
    result = answer_question(index, question)
    assert not result.grounded, (result.text, result.trace)


def test_numbered_list_is_not_returned_whole(index):
    """Regression: the whole p.145 offences list used to come back as one 'sentence'."""
    result = answer_question(index, "What should students wear on campus?")
    assert "4.1.1" not in result.text
    assert len(result.text) < 500


def test_synonym_expansion_is_shown_in_the_trace(index):
    result = answer_question(index, "What is the dress code?")
    assert any("handbook wording" in line for line in result.trace)
