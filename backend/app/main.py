import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.brain import engine
from app.brain.engine import status
from app.config import get_settings
from app.routers import admin, auth, chat, department, sources, speech, tickets, voice_dataset
from app.voice import service as voice

settings = get_settings()


def _warm_up() -> None:
    # Voice first: it's quick and it's what students wait on after every answer.
    voice.warmup()
    engine.warmup()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # In the background, so the server accepts requests while models load.
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(title="UB There", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(department.router)
app.include_router(chat.router)
app.include_router(tickets.router)
app.include_router(sources.router)
app.include_router(speech.router)
app.include_router(voice_dataset.router)
app.include_router(voice_dataset.studio_router)


@app.get("/api/health")
def health() -> dict:
    from app.voice.service import available

    return {"status": "ok", "brain": status(), "voice": available()}
