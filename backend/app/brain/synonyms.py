"""Bridges between how students ask and how the handbook words things.

The corpus-derived expansion in reflect.py only finds words that already sit next to the
query's words. It cannot help when the student's word never appears near the right
passage — "dress code" lands on the Code of Conduct because the handbook says "uniform"
and "attire". This table fills that gap.

Mappings are one-way (student wording -> handbook wording), so a question that already
uses the handbook's term is not diluted with looser words. Every target should exist in
the indexed documents; tests/test_synonyms.py checks that against the live index.
"""

from __future__ import annotations

import re

from app.brain.text import content_terms, stem

# Multi-word phrasings rewritten before tokenizing, so the filler word ("code", "out")
# does not drag the search somewhere unrelated.
PHRASES = {
    "dress code": "dress",
    "drop out": "withdraw",
    "dropping out": "withdraw",
    "kicked out": "expelled",
    "cutting class": "absent",
    "cutting classes": "absent",
    "skipping class": "absent",
    "skipping classes": "absent",
}

SYNONYMS = {
    "dress": "uniform attire",
    "clothes": "uniform attire",
    "clothing": "uniform attire",
    "outfit": "uniform attire",
    "wear": "uniform attire",
    "absent": "absence",
    "expelled": "expulsion dismissal",
    "withdraw": "withdrawal",
    "quit": "withdrawal",
    "cheat": "dishonesty plagiarism",
    "cheating": "dishonesty plagiarism",
    "bully": "bullying",
}

_PHRASE_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in PHRASES) + r")\b")

# Keyed and valued by stem, so they line up with content_terms() output.
_STEMMED = {
    stem(word): [stem(target) for target in targets.split()]
    for word, targets in SYNONYMS.items()
}


def query_concepts(question: str) -> list[list[str]]:
    """One concept per distinct query term: the term itself first, then its synonyms.

    Retrieval searches every member; grounding and confidence count a concept as covered
    when any member is present, so a synonym never counts against the answer.
    """
    text = _PHRASE_RE.sub(lambda m: PHRASES[m.group(1)], question.lower())

    concepts: list[list[str]] = []
    seen: set[str] = set()
    for term in content_terms(text):
        if term in seen:
            continue
        seen.add(term)
        concepts.append([term, *(s for s in _STEMMED.get(term, ()) if s != term)])
    return concepts


def flatten(concepts: list[list[str]]) -> list[str]:
    terms: list[str] = []
    for concept in concepts:
        terms.extend(t for t in concept if t not in terms)
    return terms
