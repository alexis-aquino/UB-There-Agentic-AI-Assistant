"""Which questions the assistant flags for the admin as offensive or off-topic.

Keyword rules, like intents.py and topics.py: quick and predictable. Flags only change the admin's report, never the student's
reply, and an administrator can clear a wrong flag or add a missed one in the Inquiry tracker.
"""

from __future__ import annotations

import re

from app.brain.topics import OTHER, topic_of

OFFENSIVE = "offensive language"
OFF_TOPIC = "not about school"

# Insults and profanity, English and Filipino. Matched as whole words or phrases. Mild words like
# "stupid" count only when aimed at someone: "is it stupid to drop a subject?" is a real question.
OFFENSIVE_WORDS = (
    "idiot", "idiots", "moron", "dumbass", "fuck", "fucking", "fck", "wtf", "shit", "bullshit",
    "bitch", "bastard", "asshole", "shut up", "useless bot", "stupid bot", "dumb bot",
    "you stupid", "you are stupid", "you're stupid", "youre stupid", "ur stupid", "so stupid",
    "you are dumb", "you're dumb", "youre dumb", "ur dumb", "you are useless", "you're useless",
    "bobo", "tanga", "gago", "gaga", "ulol", "ulul", "tangina", "tang ina", "putangina", "puta",
    "inutil", "tarantado", "leche", "bwisit", "buwisit", "pakyu", "hayop ka", "walang kwenta",
)

# Words that make a question about school, besides the topic keywords in topics.py.
SCHOOL_WORDS = (
    "school", "class", "classes", "classroom", "student", "students", "teacher", "teachers",
    "professor", "prof", "instructor", "faculty", "adviser", "advisor", "campus", "university",
    "college", "ub", "batangas", "semester", "sem", "term", "course", "courses", "program",
    "handbook", "policy", "policies", "rule", "rules", "office", "registrar", "allowed", "permit",
    "major", "minor", "section", "schedule", "thesis", "ojt", "internship", "requirement",
    "requirements", "freshman", "freshmen", "senior", "junior", "alumni", "staff", "hours",
    "deadline", "due", "form", "forms", "apply", "application", "request", "submit", "document",
)

# Clearly not school matters, even next to a school-sounding word ("NBA finals").
OFF_TOPIC_WORDS = (
    "nba", "pba", "recipe", "recipes", "adobo", "movie", "movies", "netflix", "song", "songs",
    "lyrics", "joke", "jokes", "girlfriend", "boyfriend", "crush", "weather", "celebrity",
    "kpop", "anime", "lottery", "bitcoin", "crypto", "horoscope", "zodiac",
)


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(p)}\b", text) for p in phrases)


def flag_reason(question: str, handbook_matched: bool) -> str | None:
    """Why the question should be flagged, or None. `handbook_matched`: the search found passages."""
    text = question.lower()
    if _has_any(text, OFFENSIVE_WORDS):
        return OFFENSIVE
    # Only questions the handbook didn't cover: anything it answered is about school.
    if handbook_matched:
        return None
    about_school = topic_of(question) != OTHER or _has_any(text, SCHOOL_WORDS)
    if not about_school or _has_any(text, OFF_TOPIC_WORDS):
        return OFF_TOPIC
    return None
