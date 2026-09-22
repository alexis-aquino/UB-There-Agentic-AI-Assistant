"""Generic free voice via Piper — neural TTS that runs in real time on CPU.

Piper is a peripheral, not part of the brain. It turns finished text into sound and has
no say in what the assistant answers.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

_voice = None


class PiperUnavailableError(RuntimeError):
    pass


def _load(model_name: str, download_dir: Path):
    global _voice
    if _voice is not None:
        return _voice

    try:
        from piper import PiperVoice
        from piper.download_voices import download_voice
    except ImportError as exc:
        raise PiperUnavailableError(
            "Piper is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install "
            "-r requirements-voice.txt"
        ) from exc

    download_dir.mkdir(parents=True, exist_ok=True)
    model_path = download_dir / f"{model_name}.onnx"
    if not model_path.exists():
        download_voice(model_name, download_dir)

    _voice = PiperVoice.load(str(model_path))
    return _voice


def synthesize(text: str, model_name: str, download_dir: Path) -> bytes:
    voice = _load(model_name, download_dir)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return buffer.getvalue()
