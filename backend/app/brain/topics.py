"""Which topic a student's question is about, for the admin's inquiry report.

Keyword rules, like intents.py: quick, predictable, and easy to extend. A word matches a
keyword that it starts with ("enrolling" -> "enroll"); keywords under four letters ("id",
"tor") must match exactly. The topic with the most matches wins; none at all is "Other".
"""

from __future__ import annotations

import re

OTHER = "Other"

# The order breaks ties, and is the order the dashboard lists topics in.
TOPICS: dict[str, tuple[str, ...]] = {
    "Enrollment": (
        "enroll", "enrolment", "registration", "register", "overload", "units", "unit", "drop",
        "dropping", "adding", "add", "shift", "shifting", "transfer", "admission", "admit",
        "cross", "subject", "subjects", "load",
    ),
    "Tuition & fees": (
        "tuition", "fee", "fees", "payment", "pay", "paying", "installment", "downpayment",
        "refund", "cashier", "balance", "assessment", "accounting", "miscellaneous",
    ),
    "Scholarships": ("scholar", "scholarship", "grant", "discount", "financial", "aid", "voucher"),
    "Grades & exams": (
        "grade", "grades", "exam", "exams", "examination", "midterm", "midterms", "finals", "final",
        "quiz", "gpa", "gwa", "fail", "failed", "failing", "incomplete", "inc", "passing",
        "retake", "removal", "dean", "lister", "honor", "honors", "latin",
    ),
    "Attendance": ("absent", "absence", "absences", "attendance", "late", "tardy", "tardiness", "excuse", "cutting"),
    "Uniform & dress code": (
        "uniform", "dress", "attire", "wear", "wearing", "hair", "haircut", "earring", "earrings",
        "piercing", "tattoo", "shoes", "skirt", "pants", "clothes", "clothing", "makeup", "dye",
    ),
    "Conduct & discipline": (
        "cheat", "cheating", "plagiarism", "offense", "offenses", "violation", "violations",
        "penalty", "sanction", "suspension", "suspended", "expel", "expulsion", "discipline",
        "disciplinary", "bully", "bullying", "smoking", "vape", "vaping", "alcohol", "fight",
        "hazing", "conduct", "behavior", "misconduct",
    ),
    "Student ID": ("id", "identification", "lanyard"),
    "Records & graduation": (
        "transcript", "tor", "records", "record", "diploma", "graduation", "graduate",
        "graduating", "certificate", "certification", "clearance", "credential", "credentials",
        "authentication", "documents",
    ),
    "Organizations & events": (
        "organization", "organizations", "org", "orgs", "club", "clubs", "council", "event",
        "events", "activity", "activities", "intramurals", "sports", "election", "elections",
    ),
    "Guidance & wellbeing": (
        "guidance", "counsel", "counseling", "counselling", "stress", "stressed", "anxiety",
        "depressed", "depression", "mental", "wellbeing", "wellness", "health", "clinic",
        "medical", "sick", "nurse", "doctor",
    ),
    "Library & facilities": (
        "library", "book", "books", "borrow", "borrowing", "canteen", "cafeteria", "gym",
        "parking", "wifi", "internet", "laboratory", "lab", "room", "rooms", "facility",
        "facilities", "locker", "chapel", "comfort",
    ),
}

ALL_TOPICS: list[str] = [*TOPICS, OTHER]


def _matches(word: str, keyword: str) -> bool:
    return word == keyword or (len(keyword) >= 4 and word.startswith(keyword))


def topic_of(question: str) -> str:
    words = re.findall(r"[a-z]+", question.lower())
    best, best_score = OTHER, 0
    for topic, keywords in TOPICS.items():
        score = sum(1 for word in words if any(_matches(word, k) for k in keywords))
        if score > best_score:
            best, best_score = topic, score
    return best
