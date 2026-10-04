r"""Build the sentence list you read aloud to train your Piper voice.

Most prompts come from the handbook itself, so the voice is trained on the exact words it
will later speak (registrar, enrolment, Batangas...). Hand-written lines add questions,
greetings and exclamations, which the handbook lacks but the assistant says every day.

Sentences are picked greedily to cover as many different words as possible: coverage of
sounds matters more than sheer hours for a fine-tune.

    .\.venv\Scripts\python.exe voice_training\build_prompts.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.brain.bm25 import BM25Index  # noqa: E402
from app.brain.text import split_sentences, tokenize  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / "prompts.txt"
HANDBOOK_PROMPTS = 360

CONVERSATIONAL = """
Hi there! Ask me anything about university policies and I'll look it up.
Hello, and welcome to the University of Batangas.
Good morning! How can I help you today?
Good afternoon. What would you like to know?
Good evening, and thank you for stopping by.
You're welcome! Anything else you'd like to check?
I'm glad that helped.
Take care, and good luck with your studies!
See you next time.
I couldn't find anything about that in the documents I have.
The registrar's office would be the right place to ask.
Could you rephrase that question for me?
Let me look that up in the student handbook.
Here's what the handbook says.
Here's the rule that applies.
Here's the procedure from the handbook.
Here's how the handbook defines it.
According to the handbook, that is not allowed.
That depends on your college and year level.
Are you asking about the main campus or the Lipa campus?
Did you mean the grading system or the passing grade?
Which semester are you asking about?
Is there anything else I can help you with?
Would you like me to read that again?
Yes, that is allowed with the dean's approval.
No, students may not do that inside the campus.
Wow, that's a great question!
Oh no, I'm sorry to hear that.
Really? Let me double check that for you.
Okay, here is what I found.
Sure, I can explain that.
Absolutely, go ahead and ask.
Please wait a moment while I search.
Thank you for your patience.
I'm the student assistant for the University of Batangas.
I answer questions about grading, attendance, enrolment and tuition.
I only know what is written in the student handbook.
For anything urgent, please visit the guidance office.
Remember to bring your school ID every day.
Your adviser can help you plan your subjects.
Classes resume on Monday morning.
The library opens at nine in the morning.
Don't forget to check your email for announcements.
Quick question: have you paid your tuition fee yet?
Congratulations on finishing the semester!
What's your student number?
Why don't you ask the dean's office directly?
How exciting, your graduation is coming up!
Hmm, that isn't covered in the handbook.
One moment, please.
""".strip().splitlines()

_DIGIT_RE = re.compile(r"\d")
_ALLOWED_RE = re.compile(r"^[A-Za-z ,.'?!;:()\-\"/&]+$")
# Abbreviations and dotted forms are read aloud differently from how espeak spells them
# ("Dr." vs "doctor", "P.E." vs "pee ee"), which teaches the model wrong pronunciations.
_ABBREVIATION_RE = re.compile(
    r"\b(?:Dr|Atty|Mr|Mrs|Ms|Engr|Prof|St|No|Sr|Jr|Inc|vs|etc)\.|\w\.\w|\s[A-Z]\.$|www"
)
# Acronyms espeak spells letter by letter, as people say them.
_SPELLED_ACRONYMS = {"UB", "ID"}


def readable(sentence: str) -> bool:
    """Sentences a person can read aloud one way only, with clean text for espeak."""
    if not 40 <= len(sentence) <= 170:
        return False
    if _DIGIT_RE.search(sentence) or not _ALLOWED_RE.match(sentence):
        return False
    if _ABBREVIATION_RE.search(sentence):
        return False
    if not sentence.endswith((".", "?", "!")):
        return False
    words = sentence.split()
    # PDF extraction splits words ("s tudents"); shouting headings read badly.
    if any(len(w.strip(",.;:()")) == 1 and w.strip(",.;:()") not in ("a", "A", "I") for w in words):
        return False
    bare = [w.strip(",.;:()'\"?!-") for w in words]
    if any(w.isupper() and len(w) > 1 and w not in _SPELLED_ACRONYMS for w in bare):
        return False
    return sentence[0].isupper()


def main() -> None:
    index = BM25Index.load(BACKEND / "index" / "bm25_index.json")

    candidates: list[str] = []
    seen: set[str] = set()
    for chunk in index.chunks:
        for sentence in split_sentences(chunk.text):
            key = sentence.lower()
            if key not in seen and readable(sentence):
                seen.add(key)
                candidates.append(sentence)

    # Greedy word coverage: each pick is the sentence adding the most unseen words,
    # lightly favouring shorter ones so recordings stay comfortable to read.
    covered: set[str] = set()
    picked: list[str] = []
    pool = list(candidates)
    while pool and len(picked) < HANDBOOK_PROMPTS:
        best = max(pool, key=lambda s: len(set(tokenize(s)) - covered) - len(s) / 200)
        pool.remove(best)
        picked.append(best)
        covered |= set(tokenize(best))

    # Interleave so a session never runs long stretches of formal handbook prose.
    conversational = list(CONVERSATIONAL)
    step = max(1, len(picked) // len(conversational))
    prompts: list[str] = []
    for position, sentence in enumerate(picked):
        if position % step == 0 and conversational:
            prompts.append(conversational.pop(0))
        prompts.append(sentence)
    prompts.extend(conversational)

    OUTPUT.write_text("\n".join(p.replace("|", " ") for p in prompts) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(prompts)} prompts ({len(candidates)} readable handbook sentences, "
        f"{len(covered)} distinct words covered) to {OUTPUT}"
    )


if __name__ == "__main__":
    main()
