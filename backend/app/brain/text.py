"""Tokenization, stopwords and stemming — written here rather than pulled from a library
so the whole retrieval path is ours end to end."""

import re

TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")

STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those there here
    is am are was were be been being do does did doing done have has had having
    i me my we our you your he him his she her it its they them their
    of in on at by for with about against between into through during before after
    above below to from up down out off over under again further once
    all any both each few more most other some such no nor not only own same so
    too very can will just should now what which who whom when where why how
    as also may might must shall would could s t don
    """.split()
) | frozenset(
    # Light verbs and quantifiers. These carry no topic, but they are *rare* in a formal
    # handbook, so IDF treats them as highly distinctive and they swamp the grounding
    # check — "what happens if..." would otherwise be judged on the word "happens".
    """
    happen happens happened get gets got make makes made take takes took give gives given
    go goes going come comes know knows tell tells say says said want wants need needs
    use uses used many much lot lots thing things way ways please kindly like
    """.split()
)

# Question words carry intent, so they are stripped from matching but kept for framing.
QUESTION_WORDS = frozenset("what which who whom when where why how".split())

_SUFFIXES = (
    "ational",
    "iveness",
    "fulness",
    "ousness",
    "ization",
    "ation",
    "ement",
    "ments",
    "ness",
    "ing",
    "ies",
    "ied",
    "ive",
    "ful",
    "est",
    "ers",
    "ed",
    "es",
    "ly",
    "s",
)


def stem(word: str) -> str:
    """Rule-based suffix stripper.

    Deliberately conservative: it only strips when a reasonable stem remains, so
    'class' and 'pass' survive intact while 'absences' folds to 'absenc'.
    """
    if len(word) <= 3:
        return word

    for suffix in _SUFFIXES:
        if not word.endswith(suffix):
            continue
        stemmed = word[: -len(suffix)]
        if len(stemmed) < 3:
            continue
        # A final 's' after s/u/i is part of the word, not a plural: class, campus, status.
        if suffix == "s" and stemmed[-1] in "sui":
            continue
        # 'ies' -> 'y' reads better for policy/policies, study/studies
        if suffix == "ies":
            return stemmed + "y"
        # Undouble a trailing consonant: 'dropped' -> 'drop', not 'dropp'
        if len(stemmed) > 3 and stemmed[-1] == stemmed[-2] and stemmed[-1] not in "ls":
            stemmed = stemmed[:-1]
        return _drop_silent_e(stemmed)
    return _drop_silent_e(word)


def _drop_silent_e(word: str) -> str:
    """Fold a trailing silent 'e' so singular and plural land on one stem.

    Without this, 'absence' and 'absences' stem to 'absence' and 'absenc' — two different
    keys — and a passage about absences no longer matches a question about absence.
    """
    if len(word) > 4 and word.endswith("e") and word[-2] not in "aeiou":
        return word[:-1]
    return word


def tokenize(value: str) -> list[str]:
    return TOKEN_RE.findall(value.lower())


def content_terms(value: str, keep_question_words: bool = False) -> list[str]:
    """Tokens that carry meaning for matching: stopwords out, everything stemmed."""
    terms = []
    for token in tokenize(value):
        if token in STOPWORDS and not (keep_question_words and token in QUESTION_WORDS):
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        terms.append(stem(token))
    return terms


def normalize_question(value: str) -> str:
    """Stable key for cache lookups — word order preserved, spelling folded."""
    return " ".join(content_terms(value))


SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

# Enumerated rules ("4.1.1 Shouting...; 4.1.2 Using...; ") have no sentence-ending period,
# so without this a whole list of offences reads as one sentence that matches everything.
LIST_ITEM_RE = re.compile(r"(?<=;)\s+(?=(?:\d+(?:\.\d+)+|[a-z]\.|\(?[a-z0-9]\))\s)")


_DECORATION_RE = re.compile(r"[•●■▪§∙]+")

# Running heads and folios repeat on every PDF page and otherwise leak into answers.
_BOILERPLATE_RE = re.compile(
    r"(\d{1,4}\s*\|\s*Page|Page\s*\|\s*\d{1,4}|STUDENT\s+HANDBOOK)",
    re.I,
)


def clean_text(value: str) -> str:
    """Strip bullet glyphs and collapse whitespace.

    PDF extraction leaves list markers inline, which read as noise mid-sentence and can
    break encoding when written to a Windows console.
    """
    value = value.replace("’", "'").replace("“", '"').replace("”", '"')
    value = value.replace("–", "-").replace("—", "-")
    value = _BOILERPLATE_RE.sub(" ", value)
    return " ".join(_DECORATION_RE.sub(" ", value).split())


def split_sentences(value: str) -> list[str]:
    parts = []
    for sentence in SENTENCE_END_RE.split(value):
        for raw in LIST_ITEM_RE.split(sentence):
            cleaned = " ".join(raw.split())
            if cleaned:
                parts.append(cleaned)
    return parts
