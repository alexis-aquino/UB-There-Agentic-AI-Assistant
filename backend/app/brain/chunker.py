"""Sentence-aware chunking.

A whole PDF page covers several unrelated topics, so indexing pages whole buries the
answer among noise. Splitting on sentence boundaries with overlap keeps each chunk about
one thing while stopping a fact from being cut in half at a boundary.
"""

from __future__ import annotations

from app.brain.bm25 import Chunk
from app.brain.readers import Page
from app.brain.text import clean_text, split_sentences

TARGET_WORDS = 120
OVERLAP_SENTENCES = 1


def chunk_pages(pages: list[Page], target_words: int = TARGET_WORDS) -> list[Chunk]:
    chunks: list[Chunk] = []

    for page in pages:
        page_text = clean_text(page.text)
        sentences = split_sentences(page_text) or [page_text]
        current: list[str] = []
        current_words = 0

        def flush() -> None:
            nonlocal current, current_words
            if not current:
                return
            text = " ".join(current).strip()
            if text:
                chunks.append(
                    Chunk(
                        chunk_id=len(chunks),
                        text=text,
                        source=page.source,
                        page=page.page,
                    )
                )
            current = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES else []
            current_words = sum(len(s.split()) for s in current)

        for sentence in sentences:
            words = len(sentence.split())
            if current and current_words + words > target_words:
                flush()
            current.append(sentence)
            current_words += words

        # Final flush for the page, without carrying overlap into the next page.
        if current:
            text = " ".join(current).strip()
            if text:
                chunks.append(
                    Chunk(
                        chunk_id=len(chunks),
                        text=text,
                        source=page.source,
                        page=page.page,
                    )
                )

    return chunks
