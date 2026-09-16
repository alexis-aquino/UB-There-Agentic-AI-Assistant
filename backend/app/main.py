from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat

settings = get_settings()

app = FastAPI(title="UB There — University Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)


@app.get("/api/health")
def health() -> dict:
    from app.services.providers import ProviderNotReadyError, check_ready

    try:
        check_ready()
        provider_ready, detail = True, "ready"
    except ProviderNotReadyError as exc:
        provider_ready, detail = False, str(exc)

    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "provider_ready": provider_ready,
        "detail": detail,
        "collection": settings.collection_name,
    }
