"""SQLite persistence for Glint OCR jobs.

Only metadata and the extracted text are stored - the original document bytes
are never written to the database and never kept on disk after processing.

The module intentionally uses the standard library ``sqlite3`` module with
parameterized queries only. There is no ORM and no migration tool: the schema
is created on start-up if it is missing.

Concepts demonstrated: SQL DDL/DML, parameterized queries, context managers,
exceptions, dictionaries and loops.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings

logger = logging.getLogger("glint.database")

# Columns returned to the frontend for a history *list* (the extracted text is
# deliberately left out so that listing history stays cheap).
LIST_COLUMNS = (
    "id, filename, file_type, pages, engine, duration_ms, char_count, created_at"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS ocr_jobs (
    id           TEXT PRIMARY KEY,
    filename     TEXT NOT NULL,
    file_type    TEXT NOT NULL,
    pages        INTEGER NOT NULL,
    engine       TEXT NOT NULL,
    duration_ms  REAL NOT NULL,
    char_count   INTEGER NOT NULL,
    text         TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ocr_jobs_created_at ON ocr_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_filename   ON ocr_jobs (filename);
"""

# A single lock keeps writes ordered; SQLite allows only one writer at a time.
_write_lock = threading.Lock()


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string, e.g. 2026-10-10T07:15:03Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def new_job_id() -> str:
    """A short unique identifier for one processing job."""
    return uuid.uuid4().hex[:12]


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a SQLite connection whose rows behave like dictionaries."""
    path = Path(db_path) if db_path is not None else settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA synchronous = NORMAL;")
    return connection


def init_db(db_path: Optional[Path] = None) -> Path:
    """Create the database file and tables when they do not exist yet."""
    path = Path(db_path) if db_path is not None else settings.db_path
    connection = get_connection(path)
    try:
        connection.executescript(SCHEMA)
        connection.commit()
    finally:
        connection.close()
    logger.info("SQLite database ready at %s", path.name)
    return path


def insert_job(
    *,
    filename: str,
    file_type: str,
    pages: int,
    engine: str,
    duration_ms: float,
    char_count: int,
    text: str,
    created_at: Optional[str] = None,
    job_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Store one finished OCR job and return the stored row as a dictionary."""
    record = {
        "id": job_id or new_job_id(),
        "filename": filename,
        "file_type": file_type,
        "pages": int(pages),
        "engine": engine,
        "duration_ms": round(float(duration_ms), 1),
        "char_count": int(char_count),
        "text": text,
        "created_at": created_at or utc_now_iso(),
    }
    with _write_lock:
        connection = get_connection(db_path)
        try:
            connection.execute(
                """
                INSERT INTO ocr_jobs
                    (id, filename, file_type, pages, engine,
                     duration_ms, char_count, text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["filename"],
                    record["file_type"],
                    record["pages"],
                    record["engine"],
                    record["duration_ms"],
                    record["char_count"],
                    record["text"],
                    record["created_at"],
                ),
            )
            connection.commit()
        finally:
            connection.close()
    logger.info(
        "Saved job %s (%s, %s page(s), %s chars)",
        record["id"],
        record["file_type"],
        record["pages"],
        record["char_count"],
    )
    return record


def list_jobs(
    search: Optional[str] = None,
    limit: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return recent jobs, newest first, optionally filtered by filename."""
    max_rows = limit or settings.history_page_size
    query = f"SELECT {LIST_COLUMNS} FROM ocr_jobs"
    params: List[Any] = []
    if search:
        query += " WHERE filename LIKE ?"
        params.append(f"%{search.strip()}%")
    query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
    params.append(max_rows)

    connection = get_connection(db_path)
    try:
        rows = connection.execute(query, params).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def get_job(job_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return one job including its extracted text, or ``None``."""
    connection = get_connection(db_path)
    try:
        row = connection.execute(
            "SELECT * FROM ocr_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    finally:
        connection.close()
    return dict(row) if row is not None else None


def count_jobs(db_path: Optional[Path] = None) -> int:
    """Total number of stored jobs."""
    connection = get_connection(db_path)
    try:
        row = connection.execute("SELECT COUNT(*) AS n FROM ocr_jobs").fetchone()
    finally:
        connection.close()
    return int(row["n"]) if row else 0


def delete_job(job_id: str, db_path: Optional[Path] = None) -> bool:
    """Delete one job. Returns ``True`` when a row was removed."""
    with _write_lock:
        connection = get_connection(db_path)
        try:
            cursor = connection.execute("DELETE FROM ocr_jobs WHERE id = ?", (job_id,))
            connection.commit()
            removed = cursor.rowcount
        finally:
            connection.close()
    return removed > 0


def clear_jobs(db_path: Optional[Path] = None) -> int:
    """Delete every job. Returns how many rows were removed."""
    with _write_lock:
        connection = get_connection(db_path)
        try:
            cursor = connection.execute("DELETE FROM ocr_jobs")
            connection.commit()
            removed = cursor.rowcount
            connection.execute("VACUUM")
        finally:
            connection.close()
    return max(removed, 0)


def fetch_all_jobs(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every stored job (metadata only) - used by the analytics service."""
    connection = get_connection(db_path)
    try:
        rows = connection.execute(
            f"SELECT {LIST_COLUMNS} FROM ocr_jobs ORDER BY created_at ASC"
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]
