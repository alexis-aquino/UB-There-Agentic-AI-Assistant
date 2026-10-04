"""The AI voices users can pick from in the app.

All are free Piper voices (medium quality, ~63 MB each). Only the default ships
installed; the others download into voice_models/ the first time someone uses them.
"""

from __future__ import annotations

from app.config import get_settings

VOICES: list[dict[str, str]] = [
    {"id": "en_US-lessac-medium", "name": "Lessac", "accent": "American English"},
    {"id": "en_US-amy-medium", "name": "Amy", "accent": "American English"},
    {"id": "en_US-kristin-medium", "name": "Kristin", "accent": "American English"},
    {"id": "en_US-ryan-medium", "name": "Ryan", "accent": "American English"},
    {"id": "en_US-joe-medium", "name": "Joe", "accent": "American English"},
    {"id": "en_US-john-medium", "name": "John", "accent": "American English"},
    {"id": "en_GB-alba-medium", "name": "Alba", "accent": "British English"},
    {"id": "en_GB-alan-medium", "name": "Alan", "accent": "British English"},
]


class UnknownVoiceError(ValueError):
    pass


def list_voices() -> list[dict]:
    settings = get_settings()
    default = settings.piper_voice
    voices = [dict(voice) for voice in VOICES]
    if default not in {voice["id"] for voice in voices}:
        # A voice set in .env (e.g. one trained in voice_training/) is offered first.
        voices.insert(0, {"id": default, "name": "UB There", "accent": "Custom voice"})

    for voice in voices:
        voice["default"] = voice["id"] == default
        voice["installed"] = (settings.piper_dir / f"{voice['id']}.onnx").exists()
    return voices


def resolve(voice_id: str | None) -> str:
    """The Piper model to speak with: the requested one if it is offered, else the default."""
    if not voice_id:
        return get_settings().piper_voice
    if voice_id not in {voice["id"] for voice in list_voices()}:
        raise UnknownVoiceError(f"Unknown voice '{voice_id}'.")
    return voice_id
