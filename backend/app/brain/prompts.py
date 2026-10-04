"""What the model is told. The persona and rules live here, in one place.

llama3.2 is a small model, so the prompts are shaped for it: the excerpts sit right next to
the question (small models follow what's close to the question far better than rules in a
long system prompt), and when the handbook has nothing, the model is never asked to answer
the question at all — only to say kindly that it isn't in the handbook. Asked to answer
with nothing to go on, it invents answers.
"""

from __future__ import annotations

import re
from pathlib import Path

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import NodeWithScore

SYSTEM_PROMPT = """You are UB There, a friendly student assistant at the University of Batangas.
You chat with students the way a kind, helpful upperclassman would: relaxed, warm and encouraging, using "you", contractions and everyday words.
Your replies are spoken aloud, so keep them to two to four short sentences of plain text — no markdown, no lists, no headings."""

ANSWER_TASK = """Handbook excerpts:
{excerpts}
{key_line}
The student asked: {question}

Reply like you're explaining it to a friend, using only the excerpts above.
- Answer right away, naturally. Vary how you begin — don't start with "So", "Actually", "According to the handbook" or "You're right".
- Read the rules carefully: if something isn't allowed or is limited, say so plainly.
- Keep every number and condition exactly as the excerpts state it — words like "unless", "only", "maximum", "at least" and "not" must keep their meaning.
- Only say what the excerpts say. Don't mention page numbers — the app shows the source under your reply.
- If the excerpts say nothing at all about the question, say "I couldn't find that in the handbook" and suggest tapping the "Ask an office" button below. If they cover it even partly, just share what they say."""

NOT_FOUND_TASK = """A student asked: "{question}"

The student handbook has nothing about this. Reply in one or two friendly, relaxed sentences: say you couldn't find that in the handbook, and suggest tapping the "Ask an office" button below so a university office can help. Don't start with "So" or "You're right". Do not answer the question yourself, and do not name any office, department or website."""

SMALL_TALK_TASK = """The student says: "{question}"

This is small talk, not a handbook question. Reply warmly and casually in one or two sentences, and invite them to ask anything about the student handbook."""

_DOC_WORDS = r"handbook|manual|guide|policy|policies|catalog|catalogue|rules|code"


def describe_source(label: str) -> str:
    """'studenthandbook.pdf p.99' -> 'page 99 of the student handbook'."""
    match = re.match(r"^(?P<name>.+?)(?:\s+p\.(?P<page>\d+))?$", label.strip())
    if not match:
        return label
    name = Path(match["name"]).stem
    name = re.sub(r"[_\-]+", " ", name)
    name = re.sub(rf"(?<=[a-z])(?=({_DOC_WORDS})\b)", " ", name, flags=re.I)
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name.lower().startswith("the "):
        name = f"the {name}"
    return f"page {match['page']} of {name}" if match["page"] else name


def format_excerpts(nodes: list[NodeWithScore]) -> str:
    return "\n\n".join(
        f"[From {describe_source(n.node.metadata.get('label', ''))}]\n{n.node.get_content().strip()}"
        for n in nodes
    )


# When the keyword search is sure which sentence answers the question, it's handed over
# word for word. A small model restates one sentence far more faithfully than it reads three
# passages — paraphrasing whole excerpts, llama3.2 swapped rules between groups of students.
KEY_LINE = """
The line that answers it, word for word: "{sentences}"
Base your reply on this line and keep its meaning exactly.
"""


def build_messages(
    message: str,
    nodes: list[NodeWithScore],
    history: list[ChatMessage],
    small_talk: bool,
    key_sentences: str = "",
) -> list[ChatMessage]:
    if small_talk:
        task = SMALL_TALK_TASK.format(question=message)
    elif nodes:
        key_line = KEY_LINE.format(sentences=key_sentences.strip()) if key_sentences.strip() else ""
        task = ANSWER_TASK.format(excerpts=format_excerpts(nodes), key_line=key_line, question=message)
    else:
        task = NOT_FOUND_TASK.format(question=message)
    return [
        ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
        *history,
        ChatMessage(role=MessageRole.USER, content=task),
    ]
