import io
import wave

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)
URL = "/api/voice/dataset"


def make_wav(seconds=1.5, rate=22050, channels=1, width=2):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(width)
        wav_file.setframerate(rate)
        wav_file.writeframes(b"\x00" * int(seconds * rate) * channels * width)
    return buffer.getvalue()


def upload(prompt_id, data):
    return client.post(f"{URL}/{prompt_id}", files={"file": ("clip.wav", data, "audio/wav")})


def metadata_lines():
    path = get_settings().voice_dataset_dir / "metadata.csv"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


@pytest.fixture(autouse=True)
def empty_dataset():
    for prompt_id in ("0001", "0002", "0003"):
        client.delete(f"{URL}/{prompt_id}")
    yield


def test_status_lists_every_prompt_unrecorded():
    body = client.get(URL).json()
    assert body["total"] == 3
    assert body["recorded"] == 0
    assert body["prompts"][0] == {
        "id": "0001",
        "text": "Hello, and welcome to the University of Batangas.",
        "recorded": False,
        "seconds": 0.0,
    }


def test_saved_clip_appears_in_status_and_metadata():
    response = upload("0002", make_wav(2.0))
    assert response.status_code == 200
    assert response.json()["seconds"] == 2.0

    body = client.get(URL).json()
    assert body["recorded"] == 1
    assert body["seconds"] == 2.0
    assert metadata_lines() == ["0002.wav|The library opens at nine in the morning."]


def test_metadata_follows_prompt_order_not_recording_order():
    upload("0003", make_wav())
    upload("0001", make_wav())
    assert [line.split("|")[0] for line in metadata_lines()] == ["0001.wav", "0003.wav"]


def test_redo_replaces_the_clip():
    upload("0001", make_wav(1.0))
    upload("0001", make_wav(3.0))
    assert client.get(URL).json()["seconds"] == 3.0
    assert len(metadata_lines()) == 1


def test_delete_removes_clip_and_metadata_line():
    upload("0001", make_wav())
    client.delete(f"{URL}/0001")
    assert client.get(URL).json()["recorded"] == 0
    assert metadata_lines() == []


def test_audio_is_served_back_for_playback():
    data = make_wav()
    upload("0001", data)
    response = client.get(f"{URL}/0001/audio")
    assert response.status_code == 200
    assert response.content == data
    assert client.get(f"{URL}/0002/audio").status_code == 404


@pytest.mark.parametrize(
    "data,reason",
    [
        (make_wav(rate=44100), "Expected mono 16-bit 22050 Hz"),
        (make_wav(channels=2), "Expected mono 16-bit 22050 Hz"),
        (make_wav(seconds=0.2), "between"),
        (make_wav(seconds=30), "between"),
        (b"not a wav file at all", "Not a valid WAV"),
    ],
    ids=["44khz", "stereo", "too-short", "too-long", "not-wav"],
)
def test_rejects_clips_the_trainer_cannot_use(data, reason):
    response = upload("0001", data)
    assert response.status_code == 400
    assert reason in response.json()["detail"]
    assert client.get(URL).json()["recorded"] == 0


def test_unknown_prompt_is_404():
    assert upload("9999", make_wav()).status_code == 404


def test_studio_page_is_served_by_the_backend():
    response = client.get("/voice-studio")
    assert response.status_code == 200
    assert "Voice Studio" in response.text


def test_app_frontend_cannot_reach_the_studio():
    """Recording is backend-only: a request from the student app's origin is refused."""
    headers = {"Origin": "http://localhost:5273"}
    assert client.get(URL, headers=headers).status_code == 403
    assert upload_from("0001", make_wav(), headers).status_code == 403
    assert client.get("/voice-studio", headers=headers).status_code == 403


def test_studio_refuses_requests_forwarded_by_a_proxy():
    """The frontend's dev proxy runs on this machine; a phone behind it must still be refused."""
    headers = {"X-Forwarded-For": "192.168.1.50"}
    assert client.get(URL, headers=headers).status_code == 403
    assert client.get("/voice-studio", headers=headers).status_code == 403


def test_studio_refuses_other_machines():
    remote = TestClient(app, client=("203.0.113.9", 50000))
    assert remote.get(URL).status_code == 403
    assert remote.get("/voice-studio").status_code == 403


def upload_from(prompt_id, data, headers):
    return client.post(
        f"{URL}/{prompt_id}", files={"file": ("clip.wav", data, "audio/wav")}, headers=headers
    )
