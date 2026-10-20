"""Document check (DFD process 4.0, audit uploaded documents): a student sends a photo of a
document and the AI checks it against the handbook's rules for that kind of document.

Flow: OpenAI's vision model (OPENAI_VISION_MODEL) says what the document is -> the handbook
is searched for that kind of document, the same hybrid search the chat uses -> if the
handbook has nothing about it, the check is refused -> otherwise the model compares the photo
with those passages, one requirement at a time.

The photo is never saved: it is read, sent to OpenAI for the check, and dropped. The result
(document type, verdict, what was missing) goes to the query log as the DFD's "Audit Log", so
admins and offices see it among the student query logs.
"""

from __future__ import annotations

import base64
import json
import threading
from collections import defaultdict
from datetime import date

from app.brain import engine
from app.brain.llm import ModelUnavailableError
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


class CheckError(ValueError):
    """The photo can't be checked as sent (wrong type, too big, over the daily limit)."""


IDENTIFY_TASK = """A student at the University of Batangas sent this photo to have it checked against the student handbook.
{note_line}
Look at the photo and answer in JSON only:
{{
  "is_document": true or false,       // a form, letter, certificate, ID, receipt or similar paper/card
  "readable": true or false,          // clear enough to read its text: not too blurry, dark or cut off
  "document_type": "short name",      // e.g. "excuse letter", "medical certificate", "student ID"
  "search": "words to search the handbook for the rules about this kind of document"
}}"""

CHECK_TASK = """A student sent this photo of a "{document_type}" to check it against the University of Batangas student handbook.

Handbook excerpts:
{excerpts}

Using only these excerpts, check the document in the photo. Answer in JSON only:
{{
  "covered": true or false,   // do the excerpts state any requirement for this kind of document?
  "checks": [                  // one per requirement the excerpts state for it
    {{"requirement": "what the handbook requires", "status": "met" | "missing" | "unclear", "detail": "what you see in the photo"}}
  ],
  "summary": "one or two friendly sentences for the student: is it ready, and what to fix"
}}
- Only list requirements the excerpts actually state. Don't invent any.
- "unclear" means the photo doesn't show it well enough to tell.
- If the excerpts don't state requirements for this kind of document, set "covered" to false and "checks" to []."""


def vision_json(prompt: str, image: bytes, mime: str) -> dict:
    """Ask the vision model about the photo; its JSON reply as a dict."""
    settings = get_settings()
    if not settings.openai_api_key.strip():
        raise ModelUnavailableError(
            "Checking documents needs OpenAI: set OPENAI_API_KEY in backend/.env and restart the backend."
        )
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, timeout=60.0, max_retries=2)
    url = f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
    try:
        response = client.chat.completions.create(
            model=settings.openai_vision_model,
            temperature=0,
            max_tokens=700,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        # "high": small print on forms is unreadable at low detail.
                        {"type": "image_url", "image_url": {"url": url, "detail": "high"}},
                    ],
                }
            ],
        )
    except Exception as exc:
        raise ModelUnavailableError(engine._explain_model_error(exc)) from exc
    try:
        return json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {}


def image_type(data: bytes) -> str | None:
    for magic, mime in IMAGE_TYPES.items():
        if data.startswith(magic) and (mime != "image/webp" or data[8:12] == b"WEBP"):
            return mime
    return None


# Each check costs an OpenAI call, so each student has a daily allowance. Kept in memory:
# a restart resets it, which is fine for a limit that only stops floods.
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
    mime = image_type(image)
    if mime is None:
        raise CheckError("Please send a photo (JPG, PNG or WebP).")
    _take_allowance(user_id)
    result = _check(image, mime, note)
    missing = [c["requirement"] for c in result["checks"] if c["status"] != "met"]
    engine.load().memory.log_document_check(user_id, result["document_type"], result["status"], missing)
    return result


def _check(image: bytes, mime: str, note: str) -> dict:

    note = " ".join(note.split())[:200]
    note_line = f'The student says it is: "{note}"\n' if note else ""
    seen = vision_json(IDENTIFY_TASK.format(note_line=note_line), image, mime)
    document_type = str(seen.get("document_type") or note or "document").strip()[:80]
    trace = [f"Read the photo as: {document_type}."]

    if not seen.get("is_document", True) or not seen.get("readable", True):
        return {
            "status": "unreadable",
            "document_type": document_type,
            "summary": "I couldn't read that clearly as a document. Please retake the photo in good light, "
            "with the whole page flat and in frame.",
            "checks": [],
            "citations": [],
            "trace": trace,
        }

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

    verdict = vision_json(
        CHECK_TASK.format(document_type=document_type, excerpts=format_excerpts(nodes)), image, mime
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
