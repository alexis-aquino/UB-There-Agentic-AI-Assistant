"""Hybrid search: LlamaIndex vectors plus the handbook keyword index, as one LlamaIndex retriever.

Vectors find passages that mean the same thing in different words; the keyword index finds
exact handbook terms ("overload", "TOR") that vectors can blur. Results are merged by
reciprocal rank fusion.

The keyword side also brings its grounding check — whether the question is actually covered
by the documents. When neither side is confident, the retriever returns nothing, so the model
says it couldn't find the answer instead of building one out of loosely related passages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.brain.bm25 import BM25Index
from app.brain.reflect import answer_question
from app.brain.vectors import to_cosine, to_node
from app.config import get_settings

# When is a question on-topic? Calibrated on the handbook's golden and off-topic questions
# with nomic-embed-text: on-topic best matches scored 0.645-0.822, off-topic 0.522-0.617.
#   - a strong meaning match on its own (catches paraphrases like "can i dye my hair"), or
#   - a grounded keyword match backed by a moderate meaning match (the keyword check alone
#     passed "what is 2 plus 2" by matching the digit).
# Floors: (meaning alone, meaning alongside keywords). Another embedding model needs its
# own calibration; the mock test embedding only trusts keywords.
FLOORS = {"nomic-embed-text": (0.63, 0.55), "mock": (2.0, 0.0)}
DEFAULT_FLOORS = FLOORS["nomic-embed-text"]
RRF_K = 60  # standard reciprocal-rank-fusion damping


def _floors() -> tuple[float, float]:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return FLOORS["mock"]
    return FLOORS.get(settings.ollama_embed_model.split(":")[0], DEFAULT_FLOORS)


@dataclass
class SearchReport:
    keyword_grounded: bool = False
    keyword_confidence: float = 0.0
    vector_top: float = 0.0
    relevant: bool = False
    # The exact handbook sentence(s) the keyword search picked as the answer, when it's sure.
    key_sentences: str = ""
    trace: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return max(self.keyword_confidence if self.keyword_grounded else 0.0, self.vector_top)


class HybridRetriever(BaseRetriever):
    def __init__(self, keywords: BM25Index, vectors: VectorStoreIndex, top_k: int = 4) -> None:
        super().__init__()
        self._keywords = keywords
        self._vectors = vectors.as_retriever(similarity_top_k=8)
        self._chunks = {chunk.chunk_id: chunk for chunk in keywords.chunks}
        self._top_k = top_k
        self.report = SearchReport()

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        query = query_bundle.query_str
        keyword = answer_question(self._keywords, query, top_k=8)
        vector_hits = self._vectors.retrieve(query)
        vector_top = to_cosine(vector_hits[0].score) if vector_hits else 0.0

        report = SearchReport(
            keyword_grounded=keyword.grounded,
            keyword_confidence=keyword.confidence,
            vector_top=round(vector_top or 0.0, 3),
        )
        alone, with_keywords = _floors()
        report.relevant = report.vector_top >= alone or (
            keyword.grounded and report.vector_top >= with_keywords
        )
        if report.relevant and keyword.grounded:
            report.key_sentences = keyword.text
        report.trace = [
            f"Keyword search: {'found' if keyword.grounded else 'no'} grounded match "
            f"(confidence {keyword.confidence:.2f}).",
            f"Meaning search (LlamaIndex + ChromaDB): best match {report.vector_top:.2f}.",
        ]
        self.report = report
        if not report.relevant:
            report.trace.append("Neither search was confident — not giving the model any excerpts.")
            return []

        scores: dict[int, float] = {}
        for rank, hit in enumerate(keyword.hits):
            scores[hit.chunk.chunk_id] = scores.get(hit.chunk.chunk_id, 0.0) + 1 / (RRF_K + rank)
        for rank, hit in enumerate(vector_hits):
            chunk_id = int(hit.node.node_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank)

        best = sorted(scores, key=scores.get, reverse=True)[: self._top_k]
        nodes = [NodeWithScore(node=to_node(self._chunks[i]), score=scores[i]) for i in best if i in self._chunks]
        report.trace.append(
            "Gave the model: " + ", ".join(n.node.metadata["label"] for n in nodes) + "."
        )
        return nodes
