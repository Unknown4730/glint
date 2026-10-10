"""Tests for the SQLite layer (stdlib sqlite3, parameterized queries)."""

from __future__ import annotations

from app import database


def _job(**overrides):
    payload = {
        "filename": "invoice.pdf",
        "file_type": "pdf",
        "pages": 3,
        "engine": "RapidOCR test - PP-OCRv6 small (ONNX Runtime, CPU)",
        "duration_ms": 1234.5,
        "char_count": 42,
        "text": "hello world",
    }
    payload.update(overrides)
    return database.insert_job(**payload)


def test_init_db_creates_the_table():
    path = database.init_db()
    assert path.exists()
    connection = database.get_connection()
    try:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ocr_jobs'"
        ).fetchone()
    finally:
        connection.close()
    assert row is not None


def test_insert_job_returns_a_complete_record():
    record = _job()
    assert len(record["id"]) == 12
    assert record["filename"] == "invoice.pdf"
    assert record["pages"] == 3
    assert record["char_count"] == 42
    assert record["text"] == "hello world"
    assert record["created_at"].endswith("Z")
    assert database.count_jobs() == 1


def test_insert_job_stores_two_different_ids():
    first = _job(filename="a.png")
    second = _job(filename="b.png")
    assert first["id"] != second["id"]
    assert database.count_jobs() == 2


def test_get_job_returns_the_stored_text():
    record = _job(text="line one\nline two")
    fetched = database.get_job(record["id"])
    assert fetched is not None
    assert fetched["text"] == "line one\nline two"
    assert fetched["filename"] == "invoice.pdf"


def test_get_job_for_unknown_id_returns_none():
    assert database.get_job("does-not-exist") is None


def test_list_jobs_is_newest_first_and_has_no_text_column():
    first = _job(filename="older.png")
    second = _job(filename="newer.png", created_at="2026-12-31T10:00:00Z")
    rows = database.list_jobs()
    assert [row["id"] for row in rows] == [second["id"], first["id"]]
    assert "text" not in rows[0]


def test_list_jobs_search_is_case_insensitive_and_parameterized():
    _job(filename="Invoice-2026.pdf")
    _job(filename="receipt.png")
    assert len(database.list_jobs(search="invoice")) == 1
    assert len(database.list_jobs(search="RECEIPT")) == 1
    assert len(database.list_jobs(search="nothing matches")) == 0


def test_list_jobs_search_cannot_inject_sql():
    _job(filename="safe.png")
    # A classic injection attempt must be treated as a literal search string.
    assert database.list_jobs(search="'; DROP TABLE ocr_jobs; --") == []
    assert database.count_jobs() == 1


def test_list_jobs_respects_the_limit():
    for index in range(5):
        _job(filename=f"doc{index}.png")
    assert len(database.list_jobs(limit=2)) == 2


def test_delete_job_removes_only_one_row():
    keep = _job(filename="keep.png")
    remove = _job(filename="remove.png")
    assert database.delete_job(remove["id"]) is True
    assert database.delete_job(remove["id"]) is False
    assert database.get_job(keep["id"]) is not None
    assert database.count_jobs() == 1


def test_clear_jobs_removes_everything():
    for index in range(3):
        _job(filename=f"doc{index}.png")
    assert database.clear_jobs() == 3
    assert database.count_jobs() == 0
    assert database.list_jobs() == []


def test_fetch_all_jobs_returns_metadata_for_analytics():
    _job(filename="a.pdf", file_type="pdf", pages=2, duration_ms=100.0)
    _job(filename="b.png", file_type="png", pages=1, duration_ms=300.0)
    rows = database.fetch_all_jobs()
    assert len(rows) == 2
    assert sum(row["pages"] for row in rows) == 3


def test_unicode_and_long_text_survive_a_round_trip():
    long_text = ("Glint \u2014 \u00e9\u00e8\u00ea \u4f60\u597d " * 400).strip()
    record = _job(text=long_text, char_count=len(long_text))
    fetched = database.get_job(record["id"])
    assert fetched["text"] == long_text
