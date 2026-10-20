import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.routers.auth import assistant_user
from app.routers.voice_dataset import studio_only
from app.schemas import SpeakRequest
from app.voice.catalog import UnknownVoiceError, list_voices
from app.voice.service import VoiceUnavailableError, available, synthesize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["voice"])

MAX_SAMPLE_BYTES = 25 * 1024 * 1024


@router.get("/voice/status")
def voice_status() -> dict:
    return available()


@router.get("/voice/voices")
def voices() -> dict:
    """The AI voices the app offers. Picking one only matters when VOICE_PROVIDER=piper."""
    settings = get_settings()
    return {"provider": settings.voice_provider, "voices": list_voices()}


# Signed-in only: making speech is heavy work, so strangers shouldn't be able to queue it.
@router.post("/speak", dependencies=[Depends(assistant_user)])
def speak(request: SpeakRequest) -> Response:
    try:
        audio = synthesize(request.text, request.voice)
    except UnknownVoiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VoiceUnavailableError as exc:
        # 503 tells the frontend to fall back to browser speech rather than go silent.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Speech synthesis failed")
        raise HTTPException(status_code=500, detail=f"Could not synthesise speech: {exc}") from exc

    return Response(content=audio, media_type="audio/wav")


@router.post("/voice/sample", dependencies=[Depends(studio_only)])
async def upload_sample(file: UploadFile = File(...)) -> dict:
    """Reference clip for XTTS voice cloning. Recorded in the backend's voice studio."""
    settings = get_settings()
    data = await file.read()

    if not data:
        raise HTTPException(status_code=400, detail="The recording was empty.")
    if len(data) > MAX_SAMPLE_BYTES:
        raise HTTPException(status_code=400, detail="Recording too large (25 MB limit).")

    settings.voice_sample_path.parent.mkdir(parents=True, exist_ok=True)
    settings.voice_sample_path.write_bytes(data)

    # Previously cached audio is in the old voice, so it must go.
    if settings.voice_cache_dir.exists():
        for stale in settings.voice_cache_dir.glob("*.wav"):
            stale.unlink()

    return {
        "saved": True,
        "bytes": len(data),
        "path": str(settings.voice_sample_path),
        "note": "Set VOICE_PROVIDER=xtts in backend/.env and restart to use this voice.",
    }
