"""Content management (DFD process 6.0): the knowledge-base files ("Official University
Information" from the admin, "Department Information" from the offices).

Admins see each file in 'upload uni info here' against the last build's manifest (indexed,
changed, new, or removed), upload, replace or delete files, and rebuild the knowledge base in
the background. Department staff do the same for their own office's files only: a file
belongs to the office that first uploaded it, and files an admin added belong to no office.
Every change is written to a change log of who did what, and when.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.brain import build as builder
from app.brain import engine
from app.brain.llm import ModelUnavailableError, check_models
from app.brain.readers import SUPPORTED
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
# Letters, digits, spaces and a few separators: no paths, nothing a shell or browser reads oddly.
SAFE_NAME = re.compile(r"^[\w][\w .()&,'+-]{0,150}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS document_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    file TEXT,
    actor TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Which office a file came from. Kept after a delete, so the office can upload it again.
CREATE TABLE IF NOT EXISTS document_owners (
    file TEXT PRIMARY KEY,
    office_id TEXT NOT NULL
);
"""


class DocumentError(ValueError):
    """Something the uploader can fix: a bad name, type or size, a missing file, or another
    office's file."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- the audit log ----------


class AuditLog:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    def record(self, action: str, actor: str, file: str | None = None, detail: str | None = None) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO document_events (action, file, actor, detail) VALUES (?, ?, ?, ?)",
                (action, file, actor, detail),
            )
            self._connection.commit()

    def owners(self) -> dict[str, str]:
        """{file: office_id} for files an office uploaded."""
        with self._lock:
            rows = self._connection.execute("SELECT file, office_id FROM document_owners").fetchall()
        return {row["file"]: row["office_id"] for row in rows}

    def set_owner(self, file: str, office_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO document_owners (file, office_id) VALUES (?, ?)", (file, office_id)
            )
            self._connection.commit()

    def recent(self, limit: int = 50, files: set[str] | None = None) -> list[dict]:
        """The latest changes; with `files`, only those to these files, plus rebuilds."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM document_events ORDER BY id DESC LIMIT ?", (limit if files is None else 1000,)
            ).fetchall()
        if files is not None:
            rows = [row for row in rows if row["file"] is None or row["file"] in files][:limit]
        return [
            {
                "action": row["action"],
                "file": row["file"],
                "actor": row["actor"],
                "detail": row["detail"],
                "at": f"{row['created_at'].replace(' ', 'T')}Z",
            }
            for row in rows
        ]


@lru_cache
def get_audit_log() -> AuditLog:
    return AuditLog(get_settings().documents_db)


# ---------- the files ----------


def check_name(name: str) -> str:
    """The plain file name to save as, or DocumentError. Never a path."""
    name = name.strip()
    if Path(name).name != name or not SAFE_NAME.match(name):
        raise DocumentError("Use a plain file name: letters, numbers, spaces, and . - _ ( ) only.")
    if name in builder.SKIPPED:
        raise DocumentError(f"{name} is the folder's own notes and can't be replaced from here.")
    if Path(name).suffix.lower() not in SUPPORTED:
        raise DocumentError(f"Only {', '.join(sorted(SUPPORTED))} files can be added.")
    return name


def list_documents(office_id: str | None = None) -> dict:
    """Every document on disk compared with the last build, plus files the build had that are gone.
    With `office_id`, only that office's files."""
    manifest = builder.read_manifest()
    built = (manifest or {}).get("files", {})
    documents = []
    for path in builder.document_files():
        stat = path.stat()
        before = built.get(path.name)
        if before is None:
            status = "new"
        elif before["sha256"] != builder.file_hash(path):
            status = "changed"
        else:
            status = "indexed"
        documents.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": status,
                "pages": before["pages"] if before else None,
                "passages": before["passages"] if before else None,
            }
        )
    on_disk = {doc["name"] for doc in documents}
    for name, before in sorted(built.items()):
        if name not in on_disk:
            documents.append(
                {
                    "name": name,
                    "size": before["size"],
                    "modified": None,
                    "status": "removed",
                    "pages": before["pages"],
                    "passages": before["passages"],
                }
            )
    owners = get_audit_log().owners()
    for doc in documents:
        doc["office_id"] = owners.get(doc["name"])
    if office_id is not None:
        documents = [doc for doc in documents if doc["office_id"] == office_id]
    return {
        "documents": documents,
        "built_at": (manifest or {}).get("built_at"),
        # A manifest only exists for builds made since this feature; older ones can't be compared.
        "has_manifest": manifest is not None,
        "up_to_date": manifest is not None and all(doc["status"] == "indexed" for doc in documents),
        "supported": sorted(SUPPORTED),
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
    }


def _check_office(name: str, office_id: str | None, exists: bool) -> None:
    """Department staff may only touch their own office's files."""
    if office_id is None:
        return
    owner = get_audit_log().owners().get(name)
    if owner != office_id and (exists or owner is not None):
        whose = "another office" if owner else "the administration"
        raise DocumentError(f"{name} belongs to {whose}. Use a different file name, or ask an admin.")


def save_document(name: str, data: bytes, actor: str, office_id: str | None = None) -> bool:
    """Write the file into the documents folder. Returns True if it replaced one.
    `office_id`: a department uploading, which may only add new files or replace its own."""
    name = check_name(name)
    if not data:
        raise DocumentError("That file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError(f"Files can be up to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    folder = get_settings().docs_dir
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    replaced = target.exists()
    _check_office(name, office_id, replaced)
    # Write beside it, then swap: a half-written upload never takes the real file's place.
    partial = folder / f".{name}.uploading"
    partial.write_bytes(data)
    partial.replace(target)
    if office_id is not None:
        get_audit_log().set_owner(name, office_id)
    get_audit_log().record("replaced" if replaced else "added", actor, name, f"{len(data):,} bytes")
    return replaced


def delete_document(name: str, actor: str, office_id: str | None = None) -> None:
    name = check_name(name)
    path = get_settings().docs_dir / name
    if not path.is_file():
        raise DocumentError("There's no document with that name.")
    _check_office(name, office_id, True)
    path.unlink()
    get_audit_log().record("deleted", actor, name)


# ---------- rebuilding the knowledge base ----------


@dataclass
class RebuildState:
    state: str = "idle"  # idle | running | done | failed
    started_at: str | None = None
    finished_at: str | None = None
    started_by: str | None = None
    message: str | None = None

    def as_dict(self) -> dict:
        return dict(self.__dict__)


_rebuild = RebuildState()
_rebuild_lock = threading.Lock()


def rebuild_state() -> dict:
    with _rebuild_lock:
        return _rebuild.as_dict()


def is_rebuilding() -> bool:
    with _rebuild_lock:
        return _rebuild.state == "running"


def start_rebuild(actor: str, *, background: bool = True) -> dict:
    """Begin a rebuild. Raises DocumentError if one is running or the models are down."""
    global _rebuild
    try:
        check_models()
    except ModelUnavailableError as exc:
        raise DocumentError(str(exc)) from exc
    with _rebuild_lock:
        if _rebuild.state == "running":
            raise DocumentError("A rebuild is already running.")
        _rebuild = RebuildState(state="running", started_at=_now(), started_by=actor)
    get_audit_log().record("rebuild started", actor)
    if background:
        threading.Thread(target=_run_rebuild, args=(actor,), name="rebuild", daemon=True).start()
    else:
        _run_rebuild(actor)
    return rebuild_state()


def _run_rebuild(actor: str) -> None:
    global _rebuild
    try:
        result = builder.build(on_progress=logger.info)
    except Exception as exc:
        logger.exception("Rebuild failed")
        message = str(exc) if isinstance(exc, builder.BuildError) else f"The rebuild hit an error: {exc}"
        state = "failed"
        get_audit_log().record("rebuild failed", actor, detail=message)
    else:
        files = len(result.files)
        message = (
            f"{result.passages} passage{'s' * (result.passages != 1)} "
            f"from {files} file{'s' * (files != 1)}."
        )
        state = "done"
        get_audit_log().record("rebuild finished", actor, detail=message)
    # Either way the old indexes may be half-replaced: drop them so the next question reloads.
    engine.reset()
    with _rebuild_lock:
        _rebuild = RebuildState(
            state=state,
            started_at=_rebuild.started_at,
            finished_at=_now(),
            started_by=_rebuild.started_by,
            message=message,
        )
