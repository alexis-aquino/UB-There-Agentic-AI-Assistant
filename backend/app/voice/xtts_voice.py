"""Voice cloning via XTTS v2 (Coqui, idiap fork).

Zero-shot: there is no training run. XTTS conditions on a short reference recording at
synthesis time, so a clean 30-second sample is enough to sound like the speaker.

Weights are licensed non-commercial — fine for coursework and demos, not for resale.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

_model = None


class XttsUnavailableError(RuntimeError):
    pass


def _load():
    global _model
    if _model is not None:
        return _model

    try:
        import torch
        from TTS.api import TTS
    except ImportError as exc:
        raise XttsUnavailableError(
            "XTTS is not installed. Run: .\.venv\Scripts\python.exe -m pip install "
            "-r requirements-voice-clone.txt"
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    return _model


def synthesize(text: str, reference_wav: Path, language: str = "en") -> bytes:
    if not reference_wav.exists():
        raise XttsUnavailableError(
            "No voice sample recorded yet. Use 'Use my voice' in the app to record one."
        )

    model = _load()
    samples = model.tts(text=text, speaker_wav=str(reference_wav), language=language)

    # TTS returns float samples in -1..1; pack them as 16-bit PCM.
    import struct

    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, value)) * 32767)) for value in samples
    )

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(frames)
    return buffer.getvalue()
