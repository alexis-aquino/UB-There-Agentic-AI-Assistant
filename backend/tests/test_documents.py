"""Content management (DFD 6.0): admins and offices manage the knowledge-base files and rebuild it."""

import pytest
from fastapi.testclient import TestClient

from accounts import headers_for
from app import documents
from app.brain import engine
from app.config import get_settings
from app.main import app

client = TestClient(app)

POLICY = "Students must wear their ID cards inside the campus at all times. Lost IDs are replaced at the Registrar."


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A documents folder and index of their own, so the real handbook index is never touched."""
    settings = get_settings()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("Notes for whoever manages the folder.", encoding="utf-8")
    monkeypatch.setattr(settings, "docs_dir", docs)
    monkeypatch.setattr(settings, "index_dir", tmp_path / "index")
    engine.reset()
    yield docs
    engine.reset()  # later tests load the real index again


@pytest.fixture
def admin():
    return headers_for("admin")


def listing(headers):
    response = client.get("/api/admin/documents", headers=headers)
    assert response.status_code == 200
    return response.json()


def upload(headers, name, content=POLICY.encode()):
    return client.post("/api/admin/documents", files={"file": (name, content)}, headers=headers)


def rebuild_now(monkeypatch, headers):
    """The rebuild as the endpoint starts it, but finished before the call returns."""
    real = documents.start_rebuild
    monkeypatch.setattr(documents, "start_rebuild", lambda actor: real(actor, background=False))
    return client.post("/api/admin/documents/rebuild", headers=headers)


@pytest.mark.parametrize("role", ["student", "department"])
def test_only_admins_manage_documents(role):
    headers = headers_for(role, "registrar" if role == "department" else None)
    assert client.get("/api/admin/documents", headers=headers).status_code == 403
    assert upload(headers, "x.txt").status_code == 403
    assert client.post("/api/admin/documents/rebuild", headers=headers).status_code == 403


def test_upload_rebuild_and_the_assistant_answers_from_it(library, admin, monkeypatch):
    assert upload(admin, "id-policy.txt").status_code == 201
    before = listing(admin)
    assert [d["name"] for d in before["documents"]] == ["id-policy.txt"]  # README isn't a document
    assert before["documents"][0]["status"] == "new"
    assert before["up_to_date"] is False

    response = rebuild_now(monkeypatch, admin)
    assert response.status_code == 202
    after = listing(admin)
    assert after["rebuild"]["state"] == "done"
    assert after["up_to_date"] is True
    doc = after["documents"][0]
    assert doc["status"] == "indexed" and doc["passages"] >= 1

    # No restart: the next question searches the new index.
    reply = client.post(
        "/api/chat", json={"message": "Do I have to wear my ID card on campus?"}, headers=headers_for()
    ).json()
    assert any(s.startswith("id-policy.txt") for s in reply["sources"])


def test_changed_and_removed_files_show_against_the_last_build(library, admin, monkeypatch):
    upload(admin, "a.txt")
    upload(admin, "b.txt")
    rebuild_now(monkeypatch, admin)

    upload(admin, "a.txt", b"Library hours are eight to five on weekdays.")  # replace
    client.delete("/api/admin/documents/b.txt", headers=admin)
    upload(admin, "c.md", b"# Canteen\nThe canteen opens at seven.")

    status = {d["name"]: d["status"] for d in listing(admin)["documents"]}
    assert status == {"a.txt": "changed", "b.txt": "removed", "c.md": "new"}


def test_every_change_is_in_the_audit_log(library, admin, monkeypatch):
    upload(admin, "a.txt")
    upload(admin, "a.txt", b"A second version of the policy.")
    client.delete("/api/admin/documents/a.txt", headers=admin)

    events = listing(admin)["events"]
    assert [(e["action"], e["file"]) for e in events[:3]] == [
        ("deleted", "a.txt"),
        ("replaced", "a.txt"),
        ("added", "a.txt"),
    ]
    assert events[0]["actor"].startswith("admin-")


def test_rebuild_with_no_documents_fails_cleanly(library, admin, monkeypatch):
    rebuild_now(monkeypatch, admin)
    state = listing(admin)["rebuild"]
    assert state["state"] == "failed"
    assert "No readable documents" in state["message"]


@pytest.mark.parametrize(
    "name",
    ["../escape.txt", "sub/dir.txt", "..\\up.txt", ".hidden.txt", "script.exe", "README.md", "noextension"],
)
def test_unsafe_or_unsupported_names_are_refused(library, admin, name):
    response = upload(admin, name)
    assert response.status_code == 400
    assert not any(library.parent.glob("escape*"))


def test_empty_and_oversized_uploads_are_refused(library, admin, monkeypatch):
    assert upload(admin, "empty.txt", b"").status_code == 400
    monkeypatch.setattr(documents, "MAX_UPLOAD_BYTES", 10)
    assert "up to" in upload(admin, "big.txt", b"x" * 11).json()["detail"]
    assert not (library / "big.txt").exists()


def test_deleting_a_missing_file_is_a_clear_error(library, admin):
    assert client.delete("/api/admin/documents/nothing.txt", headers=admin).status_code == 400


def test_chat_waits_while_the_handbook_is_rebuilding(monkeypatch):
    monkeypatch.setattr(documents, "is_rebuilding", lambda: True)
    response = client.post("/api/chat", json={"message": "Hello"}, headers=headers_for())
    assert response.status_code == 503
    assert "being updated" in response.json()["detail"]


def test_only_one_rebuild_runs_at_a_time(library, admin, monkeypatch):
    monkeypatch.setattr(documents, "_rebuild", documents.RebuildState(state="running"))
    assert client.post("/api/admin/documents/rebuild", headers=admin).status_code == 409


# ---------- department staff: their own office's files ("Department Information") ----------


def office_upload(headers, name, content=POLICY.encode()):
    return client.post("/api/department/documents", files={"file": (name, content)}, headers=headers)


def office_listing(headers):
    response = client.get("/api/department/documents", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_an_office_uploads_and_sees_only_its_own_files(library, admin):
    registrar = headers_for("department", "registrar")
    accounting = headers_for("department", "accounting")
    assert office_upload(registrar, "registrar-fees-a.txt").status_code == 201
    assert upload(admin, "official-a.txt").status_code == 201

    names = [d["name"] for d in office_listing(registrar)["documents"]]
    assert names == ["registrar-fees-a.txt"]
    assert office_listing(accounting)["documents"] == []
    # The admin sees everything, and which office each file came from.
    owners = {d["name"]: d["office_id"] for d in listing(admin)["documents"]}
    assert owners["registrar-fees-a.txt"] == "registrar" and owners["official-a.txt"] is None
    events = office_listing(registrar)["events"]
    assert [e["file"] for e in events if e["file"]] == ["registrar-fees-a.txt"]


def test_an_office_cant_touch_other_files(library, admin):
    registrar = headers_for("department", "registrar")
    accounting = headers_for("department", "accounting")
    assert upload(admin, "official-b.txt").status_code == 201
    assert office_upload(registrar, "registrar-b.txt").status_code == 201

    refused = office_upload(accounting, "registrar-b.txt")
    assert refused.status_code == 400 and "another office" in refused.json()["detail"]
    assert "administration" in office_upload(registrar, "official-b.txt").json()["detail"]
    assert client.delete("/api/department/documents/registrar-b.txt", headers=accounting).status_code == 400
    assert client.delete("/api/department/documents/official-b.txt", headers=registrar).status_code == 400
    assert (library / "registrar-b.txt").exists() and (library / "official-b.txt").exists()


def test_an_office_replaces_and_deletes_its_own_file(library):
    registrar = headers_for("department", "registrar")
    assert office_upload(registrar, "registrar-c.txt").status_code == 201
    assert office_upload(registrar, "registrar-c.txt", b"Newer rules.").json()["replaced"] is True
    assert client.delete("/api/department/documents/registrar-c.txt", headers=registrar).status_code == 204
    assert not (library / "registrar-c.txt").exists()
    # Still the office's name, so it can put the file back.
    assert office_upload(registrar, "registrar-c.txt").status_code == 201


def test_an_office_rebuilds_so_its_file_is_used(library, monkeypatch):
    registrar = headers_for("department", "registrar")
    office_upload(registrar, "registrar-d.txt")
    real = documents.start_rebuild
    monkeypatch.setattr(documents, "start_rebuild", lambda actor: real(actor, background=False))
    assert client.post("/api/department/documents/rebuild", headers=registrar).status_code == 202
    assert office_listing(registrar)["documents"][0]["status"] == "indexed"


def test_students_and_admins_dont_use_the_office_endpoints(admin):
    for headers in (headers_for("student"), admin):
        assert client.get("/api/department/documents", headers=headers).status_code == 403
        assert office_upload(headers, "x.txt").status_code == 403
