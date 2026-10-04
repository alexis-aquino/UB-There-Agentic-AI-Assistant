"""Pictures of where an answer came from: the handbook page, with the passage highlighted.

Rendered with PyMuPDF from the original PDF in 'upload uni info here', cropped around the
highlight (or the full page), and cached as PNG so a page renders once.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.config import get_settings

DPI = 130
# How much of the page to show above and below the highlighted passage, in PDF points.
CROP_MARGIN = 90


class SourceNotFoundError(LookupError):
    pass


def parse_label(label: str) -> tuple[str, int | None]:
    """'studenthandbook.pdf p.99' -> ('studenthandbook.pdf', 99)."""
    match = re.match(r"^(?P<file>.+?)(?:\s+p\.(?P<page>\d+))?$", label.strip())
    if not match:
        return label, None
    return match["file"], int(match["page"]) if match["page"] else None


def _document(file_name: str) -> Path:
    # Only a plain file name inside the documents folder — never a path someone made up.
    if Path(file_name).name != file_name or not file_name.lower().endswith(".pdf"):
        raise SourceNotFoundError("Only PDF documents in the knowledge base can be shown.")
    path = get_settings().docs_dir / file_name
    if not path.is_file():
        raise SourceNotFoundError(f"No document called {file_name}.")
    return path


def _find(page, quote: str) -> list:
    """Where the quote is on the page. PDF text has odd line breaks and spacing, so if the
    whole quote isn't found, look for it in overlapping five-word pieces."""
    quote = " ".join(quote.split())
    if not quote:
        return []
    hits = page.search_for(quote)
    if hits:
        return hits
    words = quote.split()
    rects = []
    for start in range(0, max(1, len(words) - 4), 3):
        rects.extend(page.search_for(" ".join(words[start : start + 5])))
    unique = []
    for rect in rects:
        if not any(rect == seen for seen in unique):
            unique.append(rect)
    return unique


def render(file_name: str, page_number: int, quote: str = "", crop: bool = True) -> bytes:
    import pymupdf

    path = _document(file_name)
    settings = get_settings()
    key = hashlib.sha256(
        f"{file_name}|{path.stat().st_mtime_ns}|{page_number}|{quote}|{crop}|{DPI}".encode()
    ).hexdigest()[:32]
    cached = settings.source_cache_dir / f"{key}.png"
    if cached.exists():
        return cached.read_bytes()

    with pymupdf.open(path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise SourceNotFoundError(f"{file_name} has no page {page_number}.")
        page = doc[page_number - 1]
        rects = _find(page, quote)
        if rects:
            # Only on this in-memory copy; the PDF on disk is never changed.
            page.add_highlight_annot(rects)

        clip = None
        if crop and rects:
            top = min(r.y0 for r in rects) - CROP_MARGIN
            bottom = max(r.y1 for r in rects) + CROP_MARGIN
            clip = pymupdf.Rect(page.rect.x0, max(page.rect.y0, top), page.rect.x1, min(page.rect.y1, bottom))
        png = page.get_pixmap(dpi=DPI, clip=clip).tobytes("png")

    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(png)
    return png
