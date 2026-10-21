"""What OpenCV sees in a document photo, for the document check (app/doccheck.py).

OpenCV finds the page and straightens it, judges whether the photo is good enough to read
(sharp, well lit, enough contrast), cleans the page up for Tesseract OCR, which reads its text,
and looks for the marks a document's rules are often about: a signature or handwriting, a stamp
or seal, a pasted ID photo.

Nothing here decides whether a document meets a rule: the chat model does that from this
reading (see doccheck.CHECK_TASK). The marks are found by shape and colour, not understood, so
they are passed on as evidence ("found" / "not found"), never as a verdict.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.brain.llm import ModelUnavailableError
from app.config import get_settings

# The long side a photo is scaled to: enough detail for OCR of small print, quick for OpenCV.
WORK_SIDE = 1800
WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

# Below these the page is too unclear to check, and the student is asked to retake it.
MIN_WORDS = 8
MIN_CONFIDENCE = 50  # Tesseract's mean word confidence, 0-100

MARK_NAMES = {
    "signature": "a signature or handwriting",
    "stamp": "a stamp, seal or coloured logo",
    "photo": "a pasted photo (such as an ID picture)",
}


@dataclass
class Reading:
    """One photo, read: its text, how clear it was, and the marks found on the page."""

    text: str = ""
    words: int = 0
    confidence: float = 0.0
    page_found: bool = False
    problems: list[str] = field(default_factory=list)  # "blurry", "too dark", ...
    marks: dict[str, bool] = field(default_factory=dict)

    @property
    def readable(self) -> bool:
        return self.words >= MIN_WORDS and self.confidence >= MIN_CONFIDENCE

    def describe(self) -> str:
        """The reading in words, for the model's prompt."""
        marks = "\n".join(
            f"- {MARK_NAMES[name]}: {'found' if found else 'not found'}" for name, found in self.marks.items()
        )
        return (
            f"Marks OpenCV found on the page (by shape and colour, so treat them as hints):\n{marks}\n\n"
            f"Text read from the page by OCR (it may have small reading errors):\n{self.text or '(none)'}"
        )

    def summary(self) -> list[str]:
        """What OpenCV did, for the check's trace."""
        lines = [
            "Found the page edges and straightened the page."
            if self.page_found
            else "No page edges found; read the whole photo."
        ]
        lines.append(
            f"Photo quality: {', '.join(self.problems)}." if self.problems else "Photo quality: sharp and well lit."
        )
        lines.append(f"Read {self.words} words (OCR confidence {round(self.confidence)}%).")
        found = [MARK_NAMES[name] for name, seen in self.marks.items() if seen]
        lines.append(f"Marks found: {', '.join(found)}." if found else "No signature, stamp or photo found.")
        return lines


def tesseract_cmd() -> str | None:
    """Where Tesseract is: TESSERACT_CMD, else on the PATH, else its usual Windows folder."""
    configured = get_settings().tesseract_cmd.strip()
    if configured:
        return configured if Path(configured).exists() else None
    return shutil.which("tesseract") or (str(WINDOWS_TESSERACT) if WINDOWS_TESSERACT.exists() else None)


def decode(data: bytes) -> np.ndarray | None:
    """The photo as an OpenCV image at working size, or None if it isn't a picture."""
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    longest = max(image.shape[:2])
    # Shrink big photos; enlarge small ones, which Tesseract reads badly.
    if longest > WORK_SIDE or longest < WORK_SIDE // 2:
        scale = WORK_SIDE / longest
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    return image


def read(data: bytes) -> Reading | None:
    """Everything OpenCV and Tesseract make of the photo; None if it can't be opened as one."""
    cmd = tesseract_cmd()
    if cmd is None:
        raise ModelUnavailableError(
            "Checking documents needs Tesseract OCR. Install it (https://github.com/UB-Mannheim/tesseract/wiki) "
            "and restart the backend, or set TESSERACT_CMD in backend/.env to tesseract.exe."
        )
    image = decode(data)
    if image is None:
        return None
    page, page_found = find_page(image)
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
    text, words, confidence, boxes = ocr(gray, cmd)
    return Reading(
        text=text,
        words=words,
        confidence=confidence,
        page_found=page_found,
        problems=photo_problems(gray),
        marks=find_marks(page, boxes),
    )


# ---------- the page ----------


def find_page(image: np.ndarray) -> tuple[np.ndarray, bool]:
    """The page, cut out and straightened if its four edges show; else the whole photo."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = image.shape[0] * image.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(contour) < 0.2 * area:
            break  # anything smaller isn't the page
        corners = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(corners) == 4:
            return _flatten(image, corners.reshape(4, 2).astype(np.float32)), True
    return image, False


def _flatten(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    # Order the corners top-left, top-right, bottom-right, bottom-left.
    total, diff = corners.sum(axis=1), np.diff(corners, axis=1).ravel()
    tl, br = corners[np.argmin(total)], corners[np.argmax(total)]
    tr, bl = corners[np.argmin(diff)], corners[np.argmax(diff)]
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], np.float32), target)
    return cv2.warpPerspective(image, matrix, (width, height))


def photo_problems(gray: np.ndarray) -> list[str]:
    """What makes the photo hard to read, in words a student can act on."""
    problems = []
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 60:
        problems.append("blurry")
    brightness = gray.mean()
    if brightness < 80:
        problems.append("too dark")
    elif brightness > 245:
        problems.append("washed out")
    if gray.std() < 25:
        problems.append("low contrast")
    return problems


# ---------- the text ----------


def ocr(gray: np.ndarray, cmd: str) -> tuple[str, int, float, list[tuple[int, int, int, int]]]:
    """The page's text line by line, its word count, Tesseract's mean confidence, and each
    word's box (so the mark search can skip printed text)."""
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = cmd
    # Even out shadows and uneven light, so the text is black on white everywhere.
    clean = cv2.adaptiveThreshold(
        cv2.medianBlur(gray, 3), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    data = pytesseract.image_to_data(clean, config="--psm 3", output_type=pytesseract.Output.DICT)

    lines: dict[tuple[int, int, int], list[str]] = {}
    confidences, boxes = [], []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        # Every word found is printed text for the mark search, even one read poorly.
        boxes.append((data["left"][i], data["top"][i], data["width"][i], data["height"][i]))
        confidence = float(data["conf"][i])
        if confidence < 30:
            continue
        lines.setdefault((data["block_num"][i], data["par_num"][i], data["line_num"][i]), []).append(word)
        confidences.append(confidence)
    text = "\n".join(" ".join(words) for words in lines.values())
    return text[:4000], len(confidences), float(np.mean(confidences)) if confidences else 0.0, boxes


# ---------- the marks ----------


def find_marks(page: np.ndarray, word_boxes: list[tuple[int, int, int, int]]) -> dict[str, bool]:
    # Biggest first, each one masked out of the next search: a photo's colours aren't a stamp,
    # and a stamp's rings aren't handwriting.
    photos = _photo_boxes(page, word_boxes)
    stamps = _stamp_boxes(page, photos)
    return {
        "signature": _has_signature(page, word_boxes + photos + stamps),
        "stamp": bool(stamps),
        "photo": bool(photos),
    }


Box = tuple[int, int, int, int]


def _ink(gray: np.ndarray) -> np.ndarray:
    """Ink (dark marks on the paper) as white on black."""
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)


def _inside_margin(page: np.ndarray, skip: list[Box] = ()) -> np.ndarray:
    """A mask that leaves out a thin border, where page edges and shadows sit, and the boxes in `skip`."""
    height, width = page.shape[:2]
    mask = np.zeros((height, width), np.uint8)
    mask[int(height * 0.03) : int(height * 0.97), int(width * 0.03) : int(width * 0.97)] = 255
    for x, y, w, h in skip:
        cv2.rectangle(mask, (x - 3, y - 3), (x + w + 3, y + h + 3), 0, -1)
    return mask


def _photo_boxes(page: np.ndarray, word_boxes: list[Box]) -> list[Box]:
    """Pasted pictures: framed, roughly square boxes full of mid-tones (a face, a scene), with
    little printed text in them."""
    height, width = page.shape[:2]
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
    edges = cv2.dilate(cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150), np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (0.01 * height * width <= w * h <= 0.35 * height * width) or not (0.5 < w / h < 1.6):
            continue
        if cv2.contourArea(contour) < 0.7 * w * h:
            continue  # not a box
        inside = gray[y : y + h, x : x + w]
        midtones = np.count_nonzero((inside > 50) & (inside < 200)) / inside.size
        words = sum(1 for bx, by, _, _ in word_boxes if x <= bx < x + w and y <= by < y + h)
        if inside.std() > 35 and midtones > 0.4 and words < 3:
            found.append((x, y, w, h))
    return found


def _stamp_boxes(page: np.ndarray, skip: list[Box]) -> list[Box]:
    """Stamps, seals or coloured logos: sizeable, roughly round or square patches of coloured
    ink (red, blue, violet or green), outside the letterhead at the top."""
    height, width = page.shape[:2]
    hsv = cv2.cvtColor(page, cv2.COLOR_BGR2HSV)
    colour = cv2.inRange(hsv, (0, 70, 50), (179, 255, 240))
    colour = cv2.bitwise_and(colour, _inside_margin(page, skip))
    colour[: int(height * 0.12)] = 0  # the letterhead
    colour = cv2.morphologyEx(colour, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(colour)
    return [
        (int(x), int(y), int(w), int(h))
        for x, y, w, h, area in stats[1:count]
        if w * h >= height * width * 0.004 and 0.5 < w / h < 2 and area >= 0.2 * w * h
    ]


def _has_signature(page: np.ndarray, skip: list[Box]) -> bool:
    """Handwriting: wide, thin-stroked ink that isn't printed words (OCR's boxes), a photo, a
    stamp, or a straight ruled line."""
    height, width = page.shape[:2]
    ink = _ink(cv2.cvtColor(page, cv2.COLOR_BGR2GRAY))
    ink = cv2.bitwise_and(ink, _inside_margin(page, skip))
    # Join a signature's strokes into one shape.
    joined = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(joined)
    for x, y, w, h, _area in stats[1:count]:
        if w < width * 0.08 or not (height * 0.015 < h < height * 0.2):
            continue  # too small to be a signature, a ruled line, or a big block
        strokes = cv2.countNonZero(ink[y : y + h, x : x + w]) / float(w * h)
        if 0.02 < strokes < 0.3:  # thin pen strokes, not a filled shape
            return True
    return False
