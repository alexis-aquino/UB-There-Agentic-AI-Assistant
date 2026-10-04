"""Voice provider switch and on-disk audio cache.

The brain already caches answers, so the same wording recurs often — caching the audio
by text hash makes those replies play instantly instead of re-synthesising.
"""

from __future__ import annotations

import hashlib

from app.config import get_settings
from app.voice.catalog import resolve


class VoiceUnavailableError(RuntimeError):
    """No voice backend is usable — the caller should fall back to browser speech."""


def _cache_path(text: str, provider: str, voice: str):
    settings = get_settings()
    # The voice is part of the key: switching voices must not keep replaying audio
    # cached in the previous one.
    key = hashlib.sha256(f"{provider}:{voice}:{text}".encode("utf-8")).hexdigest()[:24]
    return settings.voice_cache_dir / f"{key}.wav"


def warmup() -> None:
    """Load the default voice at startup, so the first reply doesn't wait seconds for it."""
    settings = get_settings()
    if settings.voice_provider != "piper":
        return
    try:
        from app.voice.piper_voice import preload

        preload(settings.piper_voice, settings.piper_dir)
    except Exception as exc:  # best effort; speaking reports errors properly
        import logging

        logging.getLogger(__name__).warning("Voice warm-up skipped: %s", exc)


def available() -> dict:
    """Report which backends can actually run, without importing heavy modules."""
    import importlib.util

    settings = get_settings()
    return {
        "provider": settings.voice_provider,
        "piper_voice": settings.piper_voice,
        "piper_installed": importlib.util.find_spec("piper") is not None,
        "xtts_installed": importlib.util.find_spec("TTS") is not None,
        "voice_sample_recorded": settings.voice_sample_path.exists(),
    }


def synthesize(text: str, voice: str | None = None) -> bytes:
    """Speak text. `voice` picks a Piper voice from the catalog; it is ignored for XTTS,
    which always speaks in the cloned voice."""
    settings = get_settings()
    provider = settings.voice_provider

    if provider == "off":
        raise VoiceUnavailableError("Voice output is turned off (VOICE_PROVIDER=off).")

    text = text.strip()
    if not text:
        raise VoiceUnavailableError("Nothing to speak.")

    model = resolve(voice) if provider == "piper" else provider
    cached = _cache_path(text, provider, model)
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
            audio = piper_synth(text, model, settings.piper_dir)
        except PiperUnavailableError as exc:
            raise VoiceUnavailableError(str(exc)) from exc

    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(audio)
    return audio
