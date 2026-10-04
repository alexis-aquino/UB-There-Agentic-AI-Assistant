"""'Where I got this': citations on answers, and the picture of the source page."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)
HANDBOOK = "studenthandbook.pdf"
EARRINGS = "Wearing of earrings is not allowed for male students"


@pytest.fixture
def handbook():
    if not (get_settings().docs_dir / HANDBOOK).exists():
        pytest.skip("The student handbook PDF isn't in the documents folder.")


def image(**params):
    return client.get("/api/sources/image", params=params)


def test_source_page_picture_is_a_png(handbook):
    response = image(file=HANDBOOK, page=99, quote=EARRINGS)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_cropped_picture_is_smaller_than_the_full_page(handbook):
    cropped = image(file=HANDBOOK, page=99, quote=EARRINGS, crop=True).content
    full = image(file=HANDBOOK, page=99, quote=EARRINGS, crop=False).content
    assert len(cropped) < len(full)


@pytest.mark.parametrize(
    "file",
    ["../backend/.env", "..\\backend\\users.db", "notes.txt", "missing.pdf"],
)
def test_only_pdfs_in_the_documents_folder_can_be_shown(file):
    assert image(file=file, page=1).status_code == 404


def test_page_out_of_range(handbook):
    assert image(file=HANDBOOK, page=9999).status_code == 404


def test_answers_say_where_they_came_from(index):
    body = client.post("/api/chat", json={"message": "Can male students wear earrings?", "session_id": "cite"}).json()
    first = body["citations"][0]
    assert first["file"] == HANDBOOK and isinstance(first["page"], int)
    assert first["image"] is True and first["quote"]
    assert body["sources"][0] == first["label"]


def test_no_citations_when_nothing_was_found(index):
    body = client.post("/api/chat", json={"message": "What is the capital of France?", "session_id": "cite2"}).json()
    assert body["citations"] == []
