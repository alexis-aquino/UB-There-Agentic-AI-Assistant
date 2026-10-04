"""Okapi BM25, implemented directly.

BM25 scores a document by how many query terms it contains, weighted by how rare each
term is (IDF) and damped so repeating a term stops helping (saturation), with a penalty
for long documents. Term-based scoring means every result can be explained by pointing at
the terms that matched — which the reflection loop depends on.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from app.brain.text import content_terms

K1 = 1.5  # term-frequency saturation
B = 0.75  # length-normalization strength


@dataclass
class Chunk:
    chunk_id: int
    text: str
    source: str
    page: str | None = None

    def label(self) -> str:
        return f"{self.source} p.{self.page}" if self.page else self.source


@dataclass
class SearchHit:
    chunk: Chunk
    score: float
    matched_terms: list[str] = field(default_factory=list)


class BM25Index:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.doc_terms: list[list[str]] = []
        self.doc_len: list[int] = []
        self.postings: dict[str, dict[int, int]] = {}
        self.avg_len: float = 0.0

    # ---------- build ----------

    def add(self, chunk: Chunk) -> None:
        terms = content_terms(chunk.text)
        index = len(self.chunks)
        self.chunks.append(chunk)
        self.doc_terms.append(terms)
        self.doc_len.append(len(terms))

        counts: dict[str, int] = {}
        for term in terms:
            counts[term] = counts.get(term, 0) + 1
        for term, count in counts.items():
            self.postings.setdefault(term, {})[index] = count

    def finalize(self) -> None:
        self.avg_len = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0

    # ---------- search ----------

    def idf(self, term: str) -> float:
        n_docs = len(self.chunks)
        n_with = len(self.postings.get(term, {}))
        if n_with == 0:
            return 0.0
        # +1 keeps the value positive even for terms present in every document.
        return math.log(1 + (n_docs - n_with + 0.5) / (n_with + 0.5))

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        return self.search_terms(content_terms(query), top_k)

    def search_terms(self, terms: list[str], top_k: int = 5) -> list[SearchHit]:
        return self.search_concepts([[term] for term in dict.fromkeys(terms)], top_k)

    def search_concepts(self, concepts: list[list[str]], top_k: int = 5) -> list[SearchHit]:
        """BM25 where each concept (a term plus its synonyms) scores by its best member.

        Summing members instead would let a three-synonym concept outweigh the rest of
        the question — "wear slippers" would rank any uniform passage above the slippers
        rule.
        """
        if not concepts or not self.chunks:
            return []

        scores: dict[int, float] = {}
        matched: dict[int, set[str]] = {}

        for concept in concepts:
            best: dict[int, float] = {}
            for term in dict.fromkeys(concept):
                postings = self.postings.get(term)
                if not postings:
                    continue
                idf = self.idf(term)
                for doc_id, freq in postings.items():
                    norm = 1 - B + B * (self.doc_len[doc_id] / self.avg_len if self.avg_len else 1)
                    contribution = idf * (freq * (K1 + 1)) / (freq + K1 * norm)
                    best[doc_id] = max(best.get(doc_id, 0.0), contribution)
                    matched.setdefault(doc_id, set()).add(term)
            for doc_id, contribution in best.items():
                scores[doc_id] = scores.get(doc_id, 0.0) + contribution

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [
            SearchHit(
                chunk=self.chunks[doc_id],
                score=round(score, 4),
                matched_terms=sorted(matched.get(doc_id, ())),
            )
            for doc_id, score in ranked
        ]

    def known_terms(self, terms: list[str]) -> tuple[list[str], list[str]]:
        """Split query terms into those present in the corpus and those absent."""
        known = [t for t in terms if t in self.postings]
        unknown = [t for t in terms if t not in self.postings]
        return known, unknown

    # ---------- persistence ----------

    def to_dict(self) -> dict:
        return {
            "chunks": [
                {"chunk_id": c.chunk_id, "text": c.text, "source": c.source, "page": c.page}
                for c in self.chunks
            ],
            "doc_terms": self.doc_terms,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        data = json.loads(path.read_text(encoding="utf-8"))
        index = cls()
        for raw, terms in zip(data["chunks"], data["doc_terms"]):
            chunk = Chunk(
                chunk_id=raw["chunk_id"],
                text=raw["text"],
                source=raw["source"],
                page=raw["page"],
            )
            doc_id = len(index.chunks)
            index.chunks.append(chunk)
            index.doc_terms.append(terms)
            index.doc_len.append(len(terms))
            counts: dict[str, int] = {}
            for term in terms:
                counts[term] = counts.get(term, 0) + 1
            for term, count in counts.items():
                index.postings.setdefault(term, {})[doc_id] = count
        index.finalize()
        return index
