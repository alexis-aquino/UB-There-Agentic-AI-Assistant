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
async def health() -> dict:
    return {
        "status": "ok",
        "openai_key_configured": bool(settings.openai_api_key),
        "collection": settings.chroma_collection,
    }
