"""Document check (DFD process 4.0, audit uploaded documents): a student sends a photo of a
document and it is checked against the handbook's rules for that kind of document.

Flow: OpenCV finds the page, straightens it and judges the photo, Tesseract OCR reads its text,
and OpenCV looks for a signature, a stamp and a pasted photo (app/vision.py) -> if the photo is
too unclear, the student is asked to retake it -> the chat's own model (LLM_PROVIDER) names the
document from that reading -> the handbook is searched for that kind of document, the same
hybrid search the chat uses -> if the handbook has nothing about it, the check is refused ->
otherwise the model compares the reading with those passages, one requirement at a time.

The photo is never saved or sent anywhere: it is read on this machine and dropped. The result
(document type, verdict, what was missing) goes to the query log as the DFD's "Audit Log", so
admins and offices see it among the student query logs.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from datetime import date

from app import vision
from app.brain import engine
from app.brain.llm import ModelUnavailableError, get_json_llm
from app.brain.prompts import format_excerpts
from app.brain.retriever import HybridRetriever
from app.config import get_settings

MAX_IMAGE_BYTES = 8 * 1024 * 1024
# What browsers and phones send; checked by the file's first bytes, not its name.
IMAGE_TYPES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",
}

RETAKE = (
    "Please retake the photo in good light, with the whole page flat, in focus and filling the frame."
)


class CheckError(ValueError):
    """The photo can't be checked as sent (wrong type, too big, over the daily limit)."""


IDENTIFY_TASK = """A student at the University of Batangas sent a photo to have it checked against the student handbook.
{note_line}
This is what was read from the photo:

{reading}

Answer in JSON only:
{{
  "is_document": true or false,       // a form, letter, certificate, ID, receipt or similar paper/card
  "document_type": "short name",      // e.g. "excuse letter", "medical certificate", "student ID"
  "search": "words to search the handbook for the rules about this kind of document"
}}"""

CHECK_TASK = """A student sent a photo of a "{document_type}" to check it against the University of Batangas student handbook.

Handbook excerpts:
{excerpts}

This is what was read from the photo:

{reading}

Using only these excerpts, check the document. Answer in JSON only:
{{
  "covered": true or false,   // do the excerpts state any requirement for this kind of document?
  "checks": [                  // one per requirement the excerpts state for it
    {{"requirement": "what the handbook requires", "status": "met" | "missing" | "unclear", "detail": "what the reading shows"}}
  ],
  "summary": "one or two friendly sentences for the student: is it ready, and what to fix"
}}
- Only list requirements the excerpts actually state. Don't invent any.
- Judge written content from the OCR text, and signatures, stamps and photos from the marks found.
- "unclear" means the reading doesn't show it well enough to tell.
- If the excerpts don't state requirements for this kind of document, set "covered" to false and "checks" to []."""


def llm_json(prompt: str) -> dict:
    """Ask the chat's model about the reading; its JSON reply as a dict ({} if it isn't JSON)."""
    try:
        reply = get_json_llm().complete(prompt).text
    except Exception as exc:
        raise ModelUnavailableError(engine._explain_model_error(exc)) from exc
    # Small models sometimes wrap the JSON in a sentence; keep the outermost object.
    start, end = reply.find("{"), reply.rfind("}")
    try:
        parsed = json.loads(reply[start : end + 1]) if start != -1 else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def image_type(data: bytes) -> str | None:
    for magic, mime in IMAGE_TYPES.items():
        if data.startswith(magic) and (mime != "image/webp" or data[8:12] == b"WEBP"):
            return mime
    return None


# Each check runs OCR and two model calls, so each student has a daily allowance. Kept in
# memory: a restart resets it, which is fine for a limit that only stops floods.
_used: dict[tuple[int, str], int] = defaultdict(int)
_used_lock = threading.Lock()


def _take_allowance(user_id: int) -> None:
    limit = get_settings().doc_checks_per_day
    key = (user_id, date.today().isoformat())
    with _used_lock:
        if _used[key] >= limit:
            raise CheckError(f"You can check up to {limit} documents a day. Please try again tomorrow.")
        _used[key] += 1


def check(image: bytes, user_id: int, note: str = "") -> dict:
    """The verdict on one photo, logged to the query log:
    status "passed" | "needs_fixing" (with checks), "denied" (the handbook has nothing on this
    kind of document), or "unreadable" (not a document, or too unclear to check)."""
    if not image:
        raise CheckError("Please choose a photo of the document.")
    if len(image) > MAX_IMAGE_BYTES:
        raise CheckError(f"That photo is too big. Please send one under {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    if image_type(image) is None:
        raise CheckError("Please send a photo (JPG, PNG or WebP).")
    _take_allowance(user_id)
    result = _check(image, note)
    missing = [c["requirement"] for c in result["checks"] if c["status"] != "met"]
    engine.load().memory.log_document_check(user_id, result["document_type"], result["status"], missing)
    return result


def _unreadable(document_type: str, summary: str, trace: list[str]) -> dict:
    return {
        "status": "unreadable",
        "document_type": document_type,
        "summary": summary,
        "checks": [],
        "citations": [],
        "trace": trace,
    }


def _check(image: bytes, note: str) -> dict:
    note = " ".join(note.split())[:200]
    reading = vision.read(image)
    if reading is None:
        raise CheckError("That file couldn't be opened as a photo. Please send a JPG, PNG or WebP picture.")
    trace = [f"OpenCV: {line}" for line in reading.summary()]

    if not reading.readable:
        why = f"The photo looks {' and '.join(reading.problems)}. " if reading.problems else ""
        return _unreadable(note or "document", f"I couldn't read that clearly as a document. {why}{RETAKE}", trace)

    note_line = f'The student says it is: "{note}"\n' if note else ""
    seen = llm_json(IDENTIFY_TASK.format(note_line=note_line, reading=reading.describe()))
    document_type = str(seen.get("document_type") or note or "document").strip()[:80]
    trace.append(f"Read the photo as: {document_type}.")
    if not seen.get("is_document", True):
        return _unreadable(document_type, f"That doesn't look like a document to me. {RETAKE}", trace)

    brain = engine.load()
    retriever = HybridRetriever(brain.keywords, brain.vectors, top_k=4)
    query = f"{document_type} requirements {seen.get('search') or ''}".strip()
    nodes = retriever.retrieve(query)
    trace.extend(retriever.report.trace)
    denied = {
        "status": "denied",
        "document_type": document_type,
        "summary": f"I can't check this one: the handbook has no rules for a {document_type}, "
        "so there's nothing to check it against.",
        "checks": [],
        "citations": [],
        "trace": trace,
    }
    if not nodes:
        return denied

    verdict = llm_json(
        CHECK_TASK.format(document_type=document_type, excerpts=format_excerpts(nodes), reading=reading.describe())
    )
    checks = [
        {
            "requirement": str(c.get("requirement", "")).strip(),
            "status": c.get("status") if c.get("status") in {"met", "missing", "unclear"} else "unclear",
            "detail": str(c.get("detail", "")).strip(),
        }
        for c in verdict.get("checks") or []
        if isinstance(c, dict) and str(c.get("requirement", "")).strip()
    ]
    if not verdict.get("covered") or not checks:
        trace.append("The handbook passages found don't state requirements for this document.")
        return denied

    passed = all(c["status"] == "met" for c in checks)
    return {
        "status": "passed" if passed else "needs_fixing",
        "document_type": document_type,
        "summary": str(verdict.get("summary") or "").strip()
        or ("It looks ready." if passed else "A few things need fixing; see the list."),
        "checks": checks,
        "citations": engine._citations(nodes, ""),
        "trace": trace,
    }
