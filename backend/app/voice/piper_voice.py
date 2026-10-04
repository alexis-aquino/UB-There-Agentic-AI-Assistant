"""Generic free voice via Piper — neural TTS that runs in real time on CPU.

Piper is a peripheral, not part of the brain. It turns finished text into sound and has
no say in what the assistant answers.
"""

from __future__ import annotations

import io
import threading
import wave
from pathlib import Path

# Loaded voices by model name. Each is ~60 MB in memory, and only voices someone has
# actually picked get loaded.
_voices: dict[str, object] = {}
_lock = threading.Lock()


class PiperUnavailableError(RuntimeError):
    pass


def _load(model_name: str, download_dir: Path):
    if model_name in _voices:
        return _voices[model_name]

    try:
        from piper import PiperVoice
        from piper.download_voices import download_voice
    except ImportError as exc:
        raise PiperUnavailableError(
            "Piper is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install "
            "-r requirements-voice.txt"
        ) from exc

    # One download at a time, so two first requests for a new voice don't both fetch it.
    with _lock:
        if model_name in _voices:
            return _voices[model_name]
        download_dir.mkdir(parents=True, exist_ok=True)
        model_path = download_dir / f"{model_name}.onnx"
        if not model_path.exists():
            try:
                download_voice(model_name, download_dir)
            except Exception as exc:
                raise PiperUnavailableError(f"Could not download the voice {model_name}: {exc}") from exc
        _voices[model_name] = PiperVoice.load(str(model_path))
        return _voices[model_name]


def preload(model_name: str, download_dir: Path) -> None:
    """Load a voice ahead of time; the first load takes a few seconds."""
    _load(model_name, download_dir)


def synthesize(text: str, model_name: str, download_dir: Path) -> bytes:
    voice = _load(model_name, download_dir)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return buffer.getvalue()
