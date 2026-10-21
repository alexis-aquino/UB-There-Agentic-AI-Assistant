"""Document check: a student's photo, checked against the handbook's rules for that document.
The OpenCV/OCR reading and the model are replaced by stand-ins; the handbook search is the real
one. OpenCV's own part (the page, photo quality, marks) is tested on drawn pages at the end."""

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from test_tickets import sign_up

from app import doccheck
from app import vision as reader  # "vision" is the fixture below
from app.main import app

client = TestClient(app)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def send(headers, image=PNG, note=""):
    return client.post(
        "/api/documents/check", files={"file": ("photo.png", image, "image/png")}, data={"note": note}, headers=headers
    )


@pytest.fixture
def vision(monkeypatch):
    """Set what OpenCV reads and what the stand-in model makes of it; records the prompts it got."""
    state = {
        "reading": reader.Reading(
            text="Excuse letter. Dear adviser, please excuse my absence on October 3. Signed, Juan",
            words=14,
            confidence=88,
            page_found=True,
            marks={"signature": True, "stamp": False, "photo": False},
        ),
        "seen": {"is_document": True, "document_type": "school uniform", "search": "uniform policy"},
        "verdict": {
            "covered": True,
            "checks": [{"requirement": "Wear the prescribed uniform", "status": "met", "detail": "Shown."}],
            "summary": "Looks right.",
        },
        "prompts": [],
    }

    def fake(prompt):
        state["prompts"].append(prompt)
        return state["seen"] if '"is_document"' in prompt else state["verdict"]

    monkeypatch.setattr(reader, "read", lambda image: state["reading"])
    monkeypatch.setattr(doccheck, "llm_json", fake)
    return state


def test_a_document_the_handbook_covers_is_checked(index, vision):
    body = send(sign_up()[0]).json()
    assert body["status"] == "passed"
    assert body["checks"][0]["status"] == "met"
    assert body["citations"]  # the pages it was checked against
    assert "Handbook excerpts:" in vision["prompts"][1]  # judged against the handbook, not memory
    assert "October 3" in vision["prompts"][1] and "a signature or handwriting: found" in vision["prompts"][1]
    assert any(line.startswith("OpenCV:") for line in body["trace"])


def test_a_missing_requirement_needs_fixing(index, vision):
    vision["verdict"]["checks"].append({"requirement": "ID worn visibly", "status": "missing", "detail": "No ID."})
    body = send(sign_up()[0]).json()
    assert body["status"] == "needs_fixing"
    assert [c["status"] for c in body["checks"]] == ["met", "missing"]


def test_a_document_the_handbook_has_nothing_on_is_denied(index, vision):
    vision["seen"] = {"is_document": True, "document_type": "fishing licence", "search": "fishing licence"}
    body = send(sign_up()[0]).json()
    assert body["status"] == "denied" and body["checks"] == []
    assert len(vision["prompts"]) == 1  # never judged: there was nothing to judge it against


def test_denied_when_the_passages_found_state_no_requirements(index, vision):
    vision["verdict"] = {"covered": False, "checks": [], "summary": ""}
    assert send(sign_up()[0]).json()["status"] == "denied"


def test_an_unclear_photo_asks_for_a_retake(index, vision):
    vision["reading"] = vision["reading"].__class__(text="Exc", words=1, confidence=31, problems=["blurry"])
    body = send(sign_up()[0]).json()
    assert body["status"] == "unreadable" and "blurry" in body["summary"]
    assert vision["prompts"] == []  # never sent to the model


def test_something_that_isnt_a_document_asks_for_a_retake(index, vision):
    vision["seen"] = {"is_document": False, "document_type": "cat", "search": ""}
    body = send(sign_up()[0]).json()
    assert body["status"] == "unreadable" and len(vision["prompts"]) == 1


def test_the_students_note_reaches_the_model(index, vision):
    send(sign_up()[0], note="my excuse letter")
    assert '"my excuse letter"' in vision["prompts"][0]


def test_only_photos_are_accepted(index, vision):
    headers = sign_up()[0]
    assert send(headers, image=b"%PDF-1.7 not a photo").status_code == 400
    assert send(headers, image=b"").status_code == 400
    too_big = PNG + b"\x00" * doccheck.MAX_IMAGE_BYTES
    assert send(headers, image=too_big).status_code == 400
    assert vision["prompts"] == []


def test_needs_a_signed_in_account():
    assert send({}).status_code == 401


def test_each_student_has_a_daily_allowance(index, vision, monkeypatch):
    monkeypatch.setattr(doccheck.get_settings(), "doc_checks_per_day", 2)
    headers = sign_up()[0]
    assert send(headers).status_code == 200 and send(headers).status_code == 200
    refused = send(headers)
    assert refused.status_code == 400 and "up to 2 documents a day" in refused.json()["detail"]


def test_without_tesseract_it_says_so(index, monkeypatch):
    monkeypatch.setattr(reader, "tesseract_cmd", lambda: None)
    response = send(sign_up()[0])
    assert response.status_code == 503 and "Tesseract" in response.json()["detail"]


def test_a_file_that_isnt_really_a_picture_is_refused(index, monkeypatch):
    monkeypatch.setattr(reader, "tesseract_cmd", lambda: "tesseract")
    response = send(sign_up()[0])  # PNG's first bytes, then nothing a decoder can read
    assert response.status_code == 400 and "couldn't be opened" in response.json()["detail"]


def test_each_check_is_logged_without_the_photo(index, vision):
    from app.brain import engine

    headers = sign_up()[0]
    vision["verdict"]["checks"].append({"requirement": "ID worn visibly", "status": "missing", "detail": ""})
    send(headers)
    me = client.get("/api/auth/me", headers=headers).json()["id"]
    logged = [e for e in engine.load().memory.query_log(1) if e["kind"] == "document" and e["user_id"] == me]
    assert logged and logged[0]["outcome"] == "needs_fixing" and logged[0]["missing"] == ["ID worn visibly"]


# ---------- OpenCV's part, on drawn pages ----------


def drawn_page(signature=False, stamp=False, photo=False):
    """A printed letter, optionally signed, stamped and with a pasted photo; and its words' boxes
    (what OCR would report)."""
    page = np.full((1100, 850, 3), 245, np.uint8)
    boxes = []
    for i in range(18):
        y = 160 + i * 34
        line = f"Line {i} of the excuse letter for the class adviser, dated today"
        cv2.putText(page, line, (70, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
        (w, h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        boxes.append((70, y - h, w, h + 4))
    cv2.line(page, (70, 900), (400, 900), (20, 20, 20), 1)  # a ruled line to sign on
    if signature:
        t = np.linspace(0, 6 * np.pi, 300)
        stroke = np.stack([100 + t * 14, 860 + 22 * np.sin(t * 1.3) * np.cos(t / 3)], 1).astype(np.int32)
        cv2.polylines(page, [stroke], False, (140, 40, 20), 2, cv2.LINE_AA)
    if stamp:
        cv2.circle(page, (650, 900), 70, (40, 40, 200), 6)
        cv2.circle(page, (650, 900), 50, (40, 40, 200), 3)
    if photo:
        noise = np.random.default_rng(1).normal(0, 30, (200, 160, 3))
        picture = np.linspace(60, 190, 160)[None, :, None] + noise
        page[120:320, 620:780] = picture.clip(0, 255).astype(np.uint8)
        cv2.rectangle(page, (620, 120), (780, 320), (0, 0, 0), 2)
    return page, boxes


@pytest.mark.parametrize(
    "drawn",
    [{}, {"signature": True}, {"stamp": True}, {"photo": True}, {"signature": True, "stamp": True, "photo": True}],
)
def test_opencv_finds_each_mark_and_nothing_else(drawn):
    page, boxes = drawn_page(**drawn)
    expected = {name: drawn.get(name, False) for name in ("signature", "stamp", "photo")}
    assert reader.find_marks(page, boxes) == expected


def test_opencv_straightens_a_page_photographed_at_an_angle():
    page, _ = drawn_page()
    photo = np.full((1400, 1200, 3), 60, np.uint8)  # a dark desk
    corners = np.float32([[0, 0], [850, 0], [850, 1100], [0, 1100]])
    tilted = np.float32([[180, 120], [1050, 170], [1000, 1300], [150, 1260]])
    cv2.warpPerspective(
        page, cv2.getPerspectiveTransform(corners, tilted), (1200, 1400), photo, borderMode=cv2.BORDER_TRANSPARENT
    )
    flat, found = reader.find_page(photo)
    assert found and abs(flat.shape[0] / flat.shape[1] - 1100 / 850) < 0.15


def test_opencv_says_when_a_photo_is_blurry_or_dark():
    gray = cv2.cvtColor(drawn_page()[0], cv2.COLOR_BGR2GRAY)
    assert reader.photo_problems(gray) == []
    assert "blurry" in reader.photo_problems(cv2.GaussianBlur(gray, (21, 21), 0))
    assert "too dark" in reader.photo_problems((gray * 0.25).astype(np.uint8))
