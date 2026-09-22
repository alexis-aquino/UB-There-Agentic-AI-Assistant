"""Voice provider switch and on-disk audio cache.

The brain already caches answers, so the same wording recurs often — caching the audio
by text hash makes those replies play instantly instead of re-synthesising.
"""

from __future__ import annotations

import hashlib

from app.config import get_settings


class VoiceUnavailableError(RuntimeError):
    """No voice backend is usable — the caller should fall back to browser speech."""


def _cache_path(text: str, provider: str):
    settings = get_settings()
    key = hashlib.sha256(f"{provider}:{text}".encode("utf-8")).hexdigest()[:24]
    return settings.voice_cache_dir / f"{key}.wav"


def available() -> dict:
    """Report which backends can actually run, without importing heavy modules."""
    import importlib.util

    settings = get_settings()
    return {
        "provider": settings.voice_provider,
        "piper_installed": importlib.util.find_spec("piper") is not None,
        "xtts_installed": importlib.util.find_spec("TTS") is not None,
        "voice_sample_recorded": settings.voice_sample_path.exists(),
    }


def synthesize(text: str) -> bytes:
    settings = get_settings()
    provider = settings.voice_provider

    if provider == "off":
        raise VoiceUnavailableError("Voice output is turned off (VOICE_PROVIDER=off).")

    text = text.strip()
    if not text:
        raise VoiceUnavailableError("Nothing to speak.")

    cached = _cache_path(text, provider)
    if cached.exists():
        return cached.read_bytes()

    if provider == "xtts":
        from app.voice.xtts_voice import XttsUnavailableError, synthesize as xtts_synth

        try:
            audio = xtts_synth(text, settings.voice_sample_path, settings.voice_language)
        except XttsUnavailableError as exc:
            raise VoiceUnavailableError(str(exc)) from exc
    else:
        from app.voice.piper_voice import PiperUnavailableError, synthesize as piper_synth

        try:
            audio = piper_synth(text, settings.piper_voice, settings.piper_dir)
        except PiperUnavailableError as exc:
            raise VoiceUnavailableError(str(exc)) from exc

    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(audio)
    return audio
