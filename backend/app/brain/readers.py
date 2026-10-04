"""Document readers. Only file-format parsing lives here — no model does the reading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


@dataclass
class Page:
    text: str
    source: str
    page: str | None = None


def read_pdf(path: Path) -> list[Page]:
    from pypdf import PdfReader

    pages = []
    reader = PdfReader(str(path))
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(Page(text=text, source=path.name, page=str(number)))
    return pages


def read_docx(path: Path) -> list[Page]:
    import docx

    document = docx.Document(str(path))
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    return [Page(text=text, source=path.name)] if text.strip() else []


def read_plain(path: Path) -> list[Page]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    return [Page(text=text, source=path.name)] if text else []


def read_file(path: Path) -> list[Page]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".docx":
        return read_docx(path)
    if suffix in {".txt", ".md"}:
        return read_plain(path)
    return []


def read_folder(folder: Path, exclude: set[str] | None = None) -> list[Page]:
    exclude = exclude or set()
    pages: list[Page] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name in exclude:
            continue
        if path.suffix.lower() not in SUPPORTED:
            continue
        pages.extend(read_file(path))
    return pages
