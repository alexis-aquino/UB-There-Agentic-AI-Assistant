from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.rag_engine import build_rag_tool

SYSTEM_PROMPT = (
    "You are UB There, an assistant for university students. "
    "Answer questions about academic policies, grading, enrollment, and tuition using the "
    "University_Handbook_Retriever tool — it is the only authoritative source you have. "
    "If the retrieved material does not cover the question, say so plainly and point the student "
    "toward the registrar rather than guessing. Keep answers short and cite the policy you relied on."
)

_agent = None


class MissingAPIKeyError(RuntimeError):
    pass


def get_agent():
    global _agent
    if _agent is None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise MissingAPIKeyError(
                "OPENAI_API_KEY is not set. Copy backend/.env.example to backend/.env and add your key."
            )

        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
        )
        _agent = create_agent(llm, [build_rag_tool()], system_prompt=SYSTEM_PROMPT)
    return _agent


def ask(message: str) -> str:
    result = get_agent().invoke({"messages": [{"role": "user", "content": message}]})
    return result["messages"][-1].content
