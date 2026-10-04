"""Rule-based intent detection.

Social turns ("hi", "thanks") should not go through retrieval at all — answering them
directly is what makes the assistant feel conversational rather than like a search box.
"""

from __future__ import annotations

import re

GREETING = "greeting"
THANKS = "thanks"
FAREWELL = "farewell"
CAPABILITY = "capability"
QUESTION = "question"

_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        GREETING,
        re.compile(
            r"^\s*(hi+|hey|hello+|good\s+(morning|afternoon|evening)|kumusta|kamusta)\b", re.I
        ),
    ),
    (THANKS, re.compile(r"\b(thanks|thank you|salamat|appreciate it)\b", re.I)),
    (FAREWELL, re.compile(r"^\s*(bye|goodbye|see you|that'?s all|paalam)\b", re.I)),
    (
        CAPABILITY,
        re.compile(
            r"(what can you do|who are you|what are you|how do you work|what do you know|help me)",
            re.I,
        ),
    ),
]

# Shapes the framing of the reply, e.g. a "how many" question wants a number.
QUESTION_TYPES: list[tuple[str, re.Pattern]] = [
    ("count", re.compile(r"\bhow (many|much|long)\b", re.I)),
    ("person", re.compile(r"\bwho\b", re.I)),
    ("time", re.compile(r"\bwhen\b", re.I)),
    ("place", re.compile(r"\bwhere\b", re.I)),
    ("reason", re.compile(r"\bwhy\b", re.I)),
    ("process", re.compile(r"\bhow (do|can|should|would)\b", re.I)),
    ("permission", re.compile(r"^\s*(can|may|am i allowed|is it allowed)\b", re.I)),
    ("definition", re.compile(r"\bwhat (is|are|does)\b", re.I)),
]


def detect_intent(message: str) -> str:
    text = message.strip()
    if not text:
        return QUESTION
    for intent, pattern in _PATTERNS:
        if pattern.search(text):
            # A greeting attached to a real question is a question.
            if intent in {GREETING, THANKS} and len(text.split()) > 6:
                continue
            return intent
    return QUESTION


def detect_question_type(message: str) -> str:
    for label, pattern in QUESTION_TYPES:
        if pattern.search(message):
            return label
    return "general"
