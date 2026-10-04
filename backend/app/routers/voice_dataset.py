"""Collects your recordings for training a Piper voice.

Each prompt in voice_training/prompts.txt gets one clip. Clips are saved exactly as
Piper's trainer reads them — voice_dataset/wavs/<id>.wav plus a metadata.csv of
"<id>.wav|<text>" lines — so the folder can be handed to voice_training/train.sh as is.

The recording studio is a page this backend serves itself (GET /voice-studio), not part
of the student app. Every route here answers only the machine running the backend, and
only pages on the backend's own origin — so the app frontend cannot reach them.

The browser converts audio to 22,050 Hz mono 16-bit WAV before upload; this side only
validates it, so the backend needs no audio libraries.
"""

from __future__ import annotations

import wave
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.config import BACKEND_ROOT, get_settings

STUDIO_PAGE = BACKEND_ROOT / "voice_training" / "studio.html"


def studio_only(request: Request) -> None:
    """Allow the voice studio only on the backend's machine, from the backend's own page."""
    host = request.client.host if request.client else ""
    # A proxy (like the frontend dev server) connects from this machine, so its requests
    # look local; the forwarded header shows they really came from elsewhere.
    forwarded = "x-forwarded-for" in request.headers
    if forwarded or host not in get_settings().studio_hosts:
        raise HTTPException(
            status_code=403,
            detail="The voice studio is only available on the computer running the backend.",
        )
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(
            status_code=403,
            detail="Voice recording is backend-only. Open /voice-studio on the backend instead.",
        )


router = APIRouter(
    prefix="/api/voice/dataset", tags=["voice-training"], dependencies=[Depends(studio_only)]
)
studio_router = APIRouter(tags=["voice-training"], dependencies=[Depends(studio_only)])


@studio_router.get("/voice-studio", include_in_schema=False)
def studio_page() -> FileResponse:
    return FileResponse(STUDIO_PAGE, media_type="text/html", headers={"Cache-Control": "no-store"})

SAMPLE_RATE = 22050
MIN_SECONDS = 0.6
MAX_SECONDS = 25.0
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# A fine-tune from the Lessac checkpoint starts sounding like you at roughly this much.
TARGET_SECONDS = 25 * 60


def _wav_dir() -> Path:
    return get_settings().voice_dataset_dir / "wavs"


def _prompts() -> list[dict]:
    path = get_settings().voice_prompts_path
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="No prompts yet. Run: .\\.venv\\Scripts\\python.exe voice_training\\build_prompts.py",
        )
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [{"id": f"{n:04d}", "text": text} for n, text in enumerate(lines, 1) if text]


def _prompt(prompt_id: str) -> dict:
    for prompt in _prompts():
        if prompt["id"] == prompt_id:
            return prompt
    raise HTTPException(status_code=404, detail=f"No prompt {prompt_id}.")


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def _write_metadata() -> None:
    """Rewrite metadata.csv from the clips on disk, so it can never drift from them."""
    wav_dir = _wav_dir()
    lines = [
        f"{prompt['id']}.wav|{prompt['text']}"
        for prompt in _prompts()
        if (wav_dir / f"{prompt['id']}.wav").exists()
    ]
    metadata = get_settings().voice_dataset_dir / "metadata.csv"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


@router.get("")
def dataset_status() -> dict:
    wav_dir = _wav_dir()
    items = []
    total_seconds = 0.0
    for prompt in _prompts():
        path = wav_dir / f"{prompt['id']}.wav"
        seconds = _duration(path) if path.exists() else 0.0
        total_seconds += seconds
        items.append({**prompt, "recorded": path.exists(), "seconds": round(seconds, 2)})

    return {
        "prompts": items,
        "recorded": sum(1 for item in items if item["recorded"]),
        "total": len(items),
        "seconds": round(total_seconds, 1),
        "target_seconds": TARGET_SECONDS,
        "sample_rate": SAMPLE_RATE,
        "dataset_dir": str(get_settings().voice_dataset_dir),
    }


@router.post("/{prompt_id}")
async def save_clip(prompt_id: str, file: UploadFile = File(...)) -> dict:
    _prompt(prompt_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The recording was empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Clip too large — keep each under 25 s.")

    wav_dir = _wav_dir()
    wav_dir.mkdir(parents=True, exist_ok=True)
    target = wav_dir / f"{prompt_id}.wav"
    temp = target.with_suffix(".tmp")
    temp.write_bytes(data)

    try:
        with wave.open(str(temp), "rb") as wav_file:
            channels = wav_file.getnchannels()
            width = wav_file.getsampwidth()
            rate = wav_file.getframerate()
            seconds = wav_file.getnframes() / rate
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        temp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Not a valid WAV file: {exc}") from exc

    problem = None
    if (channels, width, rate) != (1, 2, SAMPLE_RATE):
        problem = f"Expected mono 16-bit {SAMPLE_RATE} Hz, got {channels} ch / {width * 8}-bit / {rate} Hz."
    elif not MIN_SECONDS <= seconds <= MAX_SECONDS:
        problem = f"Clip is {seconds:.1f} s; it should be between {MIN_SECONDS} and {MAX_SECONDS} s."
    if problem:
        temp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=problem)

    temp.replace(target)
    _write_metadata()
    return {"id": prompt_id, "seconds": round(seconds, 2)}


@router.get("/{prompt_id}/audio")
def clip_audio(prompt_id: str) -> FileResponse:
    _prompt(prompt_id)
    path = _wav_dir() / f"{prompt_id}.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not recorded yet.")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.delete("/{prompt_id}")
def delete_clip(prompt_id: str) -> dict:
    _prompt(prompt_id)
    (_wav_dir() / f"{prompt_id}.wav").unlink(missing_ok=True)
    _write_metadata()
    return {"id": prompt_id, "deleted": True}
