import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.seed import seed
from app.db.session import init_db, session_scope
from app.routers import admin, auth, chat, documents, speech, tracking

logger = logging.getLogger("uvicorn.error")

settings = get_settings()

app = FastAPI(title="UB There — Agentic AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(tracking.router)
app.include_router(documents.router)
app.include_router(speech.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = session_scope()
    try:
        for note in seed(db):
            logger.warning("[setup] %s", note)
    finally:
        db.close()

    if settings.mail_mode == "live":
        logger.warning(
            "[mail] LIVE MODE — escalation emails will be sent to real addresses."
        )
    else:
        logger.info("[mail] dry-run mode: escalations are recorded but not sent.")


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
        "mail_mode": settings.mail_mode,
        "confidence_threshold": settings.confidence_threshold,
        "database": settings.database_url.split("://", 1)[0],
    }
