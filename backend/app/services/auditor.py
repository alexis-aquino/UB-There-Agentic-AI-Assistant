"""Document auditing: check a scan is legible, then read it and report what is wrong.

The point is not to reject documents but to explain how to fix them, so a student can
correct a submission before queueing at an office.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import get_settings

# Required fields per form. Empty until real UB forms are supplied — inventing
# requirements would produce confident, wrong advice.
FORM_TEMPLATES: dict[str, list[str]] = {
    "generic": [],
}


@dataclass
class Finding:
    check: str
    passed: bool
    detail: str
    how_to_fix: str = ""


@dataclass
class AuditResult:
    passed: bool
    sharpness: float
    width: int
    height: int
    findings: list[Finding] = field(default_factory=list)
    extracted_text: str = ""
    ocr_available: bool = True


def _decode(image_bytes: bytes):
    array = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def estimate_skew(gray) -> float:
    """Degrees the page is rotated, from the dominant text-line angle."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 120, minLineLength=gray.shape[1] // 3,
                            maxLineGap=20)
    if lines is None:
        return 0.0

    angles = []
    # OpenCV 4 returns (N,1,4) and OpenCV 5 returns (N,4); reshape handles both.
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -45 < angle < 45:  # near-horizontal only; verticals are borders
            angles.append(angle)
    return float(np.median(angles)) if angles else 0.0


def deskew(image, angle: float):
    if abs(angle) < 0.5:
        return image
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def run_ocr(gray) -> tuple[str, bool]:
    """Returns (text, ocr_available). Missing Tesseract is reported, not fatal."""
    settings = get_settings()
    try:
        import pytesseract
    except ImportError:
        return "", False

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    try:
        processed = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        )
        return pytesseract.image_to_string(processed).strip(), True
    except Exception:
        # Almost always "tesseract is not installed or it's not in your PATH".
        return "", False


def audit(image_bytes: bytes, form_type: str = "generic") -> AuditResult:
    settings = get_settings()
    image = _decode(image_bytes)

    if image is None:
        return AuditResult(
            passed=False,
            sharpness=0.0,
            width=0,
            height=0,
            findings=[
                Finding(
                    check="readable_file",
                    passed=False,
                    detail="The file could not be opened as an image.",
                    how_to_fix="Upload a JPG or PNG photo or scan. PDFs are not accepted here.",
                )
            ],
            ocr_available=False,
        )

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    findings: list[Finding] = []

    # --- resolution ---
    wide_enough = width >= settings.min_width
    findings.append(
        Finding(
            check="resolution",
            passed=wide_enough,
            detail=f"Image is {width}x{height} pixels.",
            how_to_fix=""
            if wide_enough
            else f"Too small to read reliably. Re-take it so the page is at least "
            f"{settings.min_width} pixels wide, filling the frame.",
        )
    )

    # --- focus ---
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharp_enough = sharpness >= settings.min_sharpness
    findings.append(
        Finding(
            check="focus",
            passed=sharp_enough,
            detail=f"Sharpness score {sharpness:.0f} (minimum {settings.min_sharpness:.0f}).",
            how_to_fix=""
            if sharp_enough
            else "The photo is blurred. Hold the camera steady, tap to focus on the text, "
            "and make sure there is enough light.",
        )
    )

    # --- lighting ---
    mean = float(gray.mean())
    spread = float(gray.std())
    # A document scan is legitimately mostly white, so a high mean is normal and must
    # not be treated as glare. What matters is that dark text stands out from the page,
    # which is what the spread measures: a blank or fogged page has almost none.
    too_dark = mean < 60
    no_contrast = spread < 18
    well_lit = not (too_dark or no_contrast)
    if too_dark:
        lighting_fix = "The page is too dark to read. Photograph it in brighter, even light."
    else:
        lighting_fix = (
            "The text barely stands out from the page. Avoid glare and shadows, and make "
            "sure the document is in focus and fully in frame."
        )
    findings.append(
        Finding(
            check="lighting",
            passed=well_lit,
            detail=f"Average brightness {mean:.0f}, contrast spread {spread:.0f}.",
            how_to_fix="" if well_lit else lighting_fix,
        )
    )

    # --- orientation ---
    angle = estimate_skew(gray)
    straight = abs(angle) <= 5
    findings.append(
        Finding(
            check="orientation",
            passed=straight,
            detail=f"Page is tilted about {angle:.1f} degrees.",
            how_to_fix=""
            if straight
            else "Straighten the page in the frame, or lay it flat and shoot from directly above.",
        )
    )

    corrected = deskew(gray, angle)
    text, ocr_available = run_ocr(corrected)

    if not ocr_available:
        findings.append(
            Finding(
                check="text_extraction",
                passed=False,
                detail="Text could not be read because Tesseract OCR is not installed.",
                how_to_fix="Install it with: winget install UB-Mannheim.TesseractOCR",
            )
        )
    else:
        has_text = len(text.split()) >= 5
        findings.append(
            Finding(
                check="text_extraction",
                passed=has_text,
                detail=f"Read {len(text.split())} words from the document.",
                how_to_fix=""
                if has_text
                else "Almost no text could be read. Check the document is right-side up and "
                "that the whole page is inside the frame.",
            )
        )

        required = FORM_TEMPLATES.get(form_type, [])
        if required:
            lowered = text.lower()
            missing = [f for f in required if f.lower() not in lowered]
            findings.append(
                Finding(
                    check="required_fields",
                    passed=not missing,
                    detail=f"Checked {len(required)} required fields for '{form_type}'.",
                    how_to_fix=""
                    if not missing
                    else f"These could not be found: {', '.join(missing)}. Fill them in, or "
                    "re-take the photo so those parts of the page are visible.",
                )
            )

    # OCR absence should not fail an otherwise good scan — the image checks are the
    # part we can stand behind without Tesseract.
    blocking = [f for f in findings if not f.passed and f.check != "text_extraction"]

    return AuditResult(
        passed=not blocking,
        sharpness=sharpness,
        width=width,
        height=height,
        findings=findings,
        extracted_text=text,
        ocr_available=ocr_available,
    )
