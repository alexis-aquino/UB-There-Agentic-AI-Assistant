"""Retrieval with a self-correction loop.

A single BM25 pass fails in predictable ways: the student's wording may not appear in the
handbook at all, or the query may match many chunks weakly instead of one strongly. Rather
than answering anyway, the loop diagnoses which of those happened, rewrites the query to
address it, retries, and finally checks the answer is actually grounded in the retrieved
text before letting it out.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.brain.bm25 import BM25Index, SearchHit
from app.brain.synonyms import flatten, query_concepts
from app.brain.text import content_terms, split_sentences

# Below this, a result is too weak to state as fact.
CONFIDENCE_FLOOR = 0.35
# A grounded answer must share at least this fraction of the query's content terms.
GROUNDING_FLOOR = 0.45


@dataclass
class Answer:
    text: str
    sources: list[str]
    confidence: float
    grounded: bool
    hits: list[SearchHit] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


def concept_weight(index: BM25Index, concept: list[str]) -> float:
    """A concept is as distinctive as its rarest member the documents actually use."""
    return max((index.idf(term) for term in concept if term in index.postings), default=0.0)


def known_concepts(index: BM25Index, concepts: list[list[str]]) -> list[list[str]]:
    """Each concept trimmed to the members the documents use; concepts with none dropped."""
    trimmed = [[term for term in concept if term in index.postings] for concept in concepts]
    return [concept for concept in trimmed if concept]


def score_confidence(hits: list[SearchHit], concepts: list[list[str]]) -> float:
    """Blend three signals: absolute strength, lead over the runner-up, and coverage."""
    if not hits:
        return 0.0

    top = hits[0]
    # Squash the unbounded BM25 score into 0..1; ~6 is a strong match in practice.
    strength = min(top.score / 6.0, 1.0)

    if len(hits) > 1 and top.score > 0:
        margin = min((top.score - hits[1].score) / top.score, 1.0)
    else:
        margin = 1.0

    matched = set(top.matched_terms)
    covered = sum(1 for concept in concepts if matched.intersection(concept))
    coverage = covered / len(concepts) if concepts else 0.0

    return round(0.5 * strength + 0.2 * margin + 0.3 * coverage, 3)


def select_sentences(
    index: BM25Index, hits: list[SearchHit], concepts: list[list[str]], limit: int = 2
) -> list[str]:
    """Pick the individual sentences that answer the question, not the whole chunk.

    Overlap is IDF-weighted: a sentence matching "students" and "campus" should not beat
    one matching "attire" and "campus", since nearly every passage mentions students.
    """
    weights = [concept_weight(index, concept) for concept in concepts]
    total = sum(weights)
    if total <= 0:
        return []
    scored: list[tuple[float, int, int, str]] = []

    for rank, hit in enumerate(hits[:3]):
        for position, sentence in enumerate(split_sentences(hit.chunk.text)):
            terms = set(content_terms(sentence))
            if not terms:
                continue
            hit_weight = sum(w for c, w in zip(concepts, weights) if terms.intersection(c))
            if not hit_weight:
                continue
            # Rescaled so it reads as a match count when every term is equally rare.
            overlap = len(concepts) * hit_weight / total
            density = overlap / len(terms) ** 0.5
            # Prefer sentences from better chunks and earlier in the chunk.
            score = overlap * 2 + density - rank * 0.5 - position * 0.05
            scored.append((score, hit.chunk.chunk_id, len(scored), sentence))

    scored.sort(key=lambda item: (-item[0], item[2]))
    if not scored:
        return []

    best_score, best_chunk, _, best_sentence = scored[0]
    chosen = [best_sentence]

    # A follow-up sentence must continue the SAME passage. Pulling the runner-up from a
    # different chunk is what made answers trail off into unrelated text.
    for score, chunk_id, _, sentence in scored[1:]:
        if len(chosen) >= limit:
            break
        if chunk_id != best_chunk or score < best_score * 0.6:
            continue
        if sentence not in chosen:
            chosen.append(sentence)
    return chosen


def is_grounded(index: BM25Index, sentences: list[str], concepts: list[list[str]]) -> bool:
    """Check the answer covers the query's *distinctive* words, not just its common ones.

    Plain term counting lets an off-topic question through: "who won the world cup in
    2018" shares 'won' and 'world' with a passage about winning competitions, which is
    half the terms but none of the meaning. Weighting coverage by IDF makes the rare
    words — the ones that actually carry the question — decide the outcome.
    """
    if not sentences or not concepts:
        return False

    covered = set()
    for sentence in sentences:
        covered |= set(content_terms(sentence))

    # Words the corpus has never seen can never be covered, so counting them here would
    # sink every answer. They are handled separately as an off-topic signal.
    wanted = known_concepts(index, concepts)
    if not wanted:
        return False

    total = sum(concept_weight(index, concept) for concept in wanted)
    if total <= 0:
        return False
    hit = sum(concept_weight(index, c) for c in wanted if covered.intersection(c))
    return (hit / total) >= GROUNDING_FLOOR


def expand_query(index: BM25Index, terms: list[str], top_k: int = 3) -> list[str]:
    """Pull in terms that co-occur with the query's terms in the corpus itself.

    This is a thesaurus derived from the documents rather than an external word list, so
    it adapts to the institution's own vocabulary.
    """
    neighbours: dict[str, float] = {}
    for term in terms:
        postings = index.postings.get(term)
        if not postings:
            continue
        for doc_id in list(postings)[:20]:
            for other in set(index.doc_terms[doc_id]):
                if other in terms:
                    continue
                neighbours[other] = neighbours.get(other, 0.0) + index.idf(other)

    ranked = sorted(neighbours.items(), key=lambda kv: kv[1], reverse=True)
    return [term for term, _ in ranked[:top_k]]


def answer_question(index: BM25Index, question: str, top_k: int = 5) -> Answer:
    trace: list[str] = []
    concepts = query_concepts(question)

    if not concepts:
        return Answer("", [], 0.0, False, [], ["Question had no searchable terms."])

    terms = flatten(concepts)
    unknown = [c[0] for c in concepts if not any(t in index.postings for t in c)]
    known = flatten(known_concepts(index, concepts))
    if unknown:
        trace.append(f"Terms not present anywhere in the documents: {', '.join(unknown)}")

    synonyms = [f"{c[0]} -> {', '.join(c[1:])}" for c in concepts if len(c) > 1]
    if synonyms:
        trace.append(f"Also searched handbook wording: {'; '.join(synonyms)}")

    # If most of the question is about things the documents never mention, it is not a
    # handbook question at all — answering would mean matching on incidental words.
    if unknown and len(unknown) >= len(concepts) * 0.5:
        trace.append("Most of this question is outside the documents' vocabulary — off topic.")
        return Answer("", [], 0.0, False, [], trace)

    # --- attempt 1 ---
    hits = index.search_concepts(concepts, top_k)
    confidence = score_confidence(hits, concepts)
    trace.append(f"Attempt 1: searched {len(terms)} terms, confidence {confidence:.2f}")

    # --- reflection ---
    if confidence < CONFIDENCE_FLOOR:
        if unknown and known:
            reason = "dropped terms the documents never use"
            retry_terms = known
            retry_concepts = known_concepts(index, concepts)
        elif known:
            reason = "added related terms found alongside these in the documents"
            extra = expand_query(index, known)
            retry_terms = known + extra
            retry_concepts = known_concepts(index, concepts) + [[term] for term in extra]
        else:
            reason = "no query term appears in the documents"
            retry_terms, retry_concepts = [], []

        trace.append(f"Confidence below {CONFIDENCE_FLOOR}; self-correcting — {reason}")

        if retry_terms:
            retry_hits = index.search_concepts(retry_concepts, top_k)
            retry_confidence = score_confidence(retry_hits, retry_concepts)
            trace.append(f"Attempt 2: confidence {retry_confidence:.2f}")
            if retry_confidence > confidence:
                hits, confidence = retry_hits, retry_confidence
                trace.append("Kept the corrected search — it scored better.")
            else:
                trace.append("Kept the original search — the correction did not improve it.")

    if not hits:
        trace.append("No matching passages.")
        return Answer("", [], 0.0, False, [], trace)

    # --- grounding check ---
    sentences = select_sentences(index, hits, concepts)
    grounded = is_grounded(index, sentences, concepts)
    trace.append(
        f"Grounding check: {'passed' if grounded else 'failed'} "
        f"({len(sentences)} candidate sentence(s))"
    )

    sources: list[str] = []
    for hit in hits[:3]:
        label = hit.chunk.label()
        if label not in sources:
            sources.append(label)

    return Answer(
        text=" ".join(sentences),
        sources=sources,
        confidence=confidence,
        grounded=grounded,
        hits=hits,
        trace=trace,
    )
