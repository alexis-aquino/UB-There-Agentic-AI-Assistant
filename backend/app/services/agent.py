from langchain.agents import create_agent

from app.services.providers import ProviderNotReadyError, build_chat_model
from app.services.rag_engine import build_rag_tool

SYSTEM_PROMPT = (
    "You are UB There, an assistant for university students. "
    "Answer questions about academic policies, grading, enrollment, and tuition using the "
    "University_Handbook_Retriever tool — it is the only source of truth you have.\n\n"
    "The tool returns passages copied from the documents, each headed by its source in square "
    "brackets like [studenthandbook.pdf p.53].\n\n"
    "Rules you must follow exactly:\n"
    "- Base every factual claim only on those passages. Never add details from memory.\n"
    "- Never invent section numbers, policy numbers, page numbers, or dates. If the passages do "
    "not give one, do not state one.\n"
    "- Never put text in quotation marks unless those exact words appear in a passage.\n"
    "- Attribute answers using only the bracketed source, e.g. 'according to studenthandbook.pdf "
    "p.53'.\n"
    "- The passages are retrieved by similarity, so some may be irrelevant. Ignore those. If none "
    "of them actually answer the question, say so plainly and suggest contacting the registrar "
    "rather than guessing.\n"
    "- Keep answers to a few sentences."
)

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(build_chat_model(), [build_rag_tool()], system_prompt=SYSTEM_PROMPT)
    return _agent


def ask(message: str) -> str:
    result = get_agent().invoke({"messages": [{"role": "user", "content": message}]})
    return result["messages"][-1].content


__all__ = ["ProviderNotReadyError", "ask", "get_agent"]
