"""Scores how well-grounded an answer is, which decides whether to escalate.

Three signals are combined. Retrieval strength and margin say whether the documents
actually contained something relevant. The refusal check reads the answer itself: when
the model says it could not find the information, that is the most reliable signal of
all, and it overrides the others.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Phrases the system prompt steers the model toward when it has nothing to answer with.
REFUSAL_PATTERNS = [
    r"couldn'?t find",
    r"could not find",
    r"do(?:es)?n'?t (?:appear|seem|contain|specify|mention)",
    r"does not (?:appear|contain|specify|mention|provide)",
    r"no information",
    r"not (?:covered|specified|mentioned|available|provided)",
    r"unable to (?:find|answer|locate)",
    r"i (?:don'?t|do not) have",
    r"contact(?:ing)? the registrar",
    r"outside (?:of )?what",
]
_REFUSAL_RE = re.compile("|".join(REFUSAL_PATTERNS), re.IGNORECASE)


@dataclass
class ConfidenceResult:
    score: float
    escalate: bool
    reason: str
    sources: list[str] = field(default_factory=list)
    refused: bool = False


def looks_like_refusal(answer: str) -> bool:
    return bool(_REFUSAL_RE.search(answer or ""))


def score_answer(
    answer: str,
    retrieval: list[dict],
    threshold: float,
    floor: float = 0.35,
    ceiling: float = 0.65,
) -> ConfidenceResult:
    sources = [item["label"] for item in retrieval]

    if not retrieval:
        return ConfidenceResult(
            score=0.0,
            escalate=True,
            reason="Nothing was retrieved from the university documents.",
            refused=looks_like_refusal(answer),
        )

    scores = sorted((item["score"] for item in retrieval), reverse=True)
    top = scores[0]
    runner_up = scores[1] if len(scores) > 1 else 0.0

    # Cosine similarity does not span 0-1 in practice. Measured against this corpus with
    # nomic-embed-text: answerable questions top out around 0.53-0.61, questions the
    # handbook does not cover land near 0.42, and unrelated ones near 0.34. So the band
    # between FLOOR and CEILING is stretched to 0-1; outside it saturates.
    # These are embedding-model specific — re-measure if the provider changes.
    span = max(ceiling - floor, 1e-6)
    strength = max(0.0, min((top - floor) / span, 1.0))
    margin = max(0.0, min((top - runner_up) / top, 1.0)) if top > 0 else 0.0

    score = round(0.85 * strength + 0.15 * margin, 3)

    refused = looks_like_refusal(answer)
    if refused:
        # The model saw the passages and still said it could not answer. Trust that over
        # the similarity numbers, which only measure lexical closeness.
        return ConfidenceResult(
            score=min(score, 0.2),
            escalate=True,
            reason="The assistant reported it could not answer from the documents.",
            sources=sources,
            refused=True,
        )

    if score < threshold:
        return ConfidenceResult(
            score=score,
            escalate=True,
            reason=f"Retrieval confidence {score:.2f} is below the {threshold:.2f} threshold.",
            sources=sources,
        )

    return ConfidenceResult(
        score=score,
        escalate=False,
        reason="Answer is well grounded in the retrieved documents.",
        sources=sources,
    )
