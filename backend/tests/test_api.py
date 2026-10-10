"""API level tests.

Everything here runs against a stubbed OCR engine, so no model is loaded and
the whole file finishes in well under a second.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from conftest import FakeOCRService, make_pdf, make_text_image, upload

# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------
def test_health_reports_ok_and_ready_ocr(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "GLINT"
    assert body["ocr"]["ready"] is True
    assert body["ocr"]["device"] == "cpu"
    assert body["database_ready"] is True
    assert body["limits"]["max_file_size_mb"] == settings.max_file_size_mb


def test_health_does_not_claim_ocr_is_ready_when_init_failed(broken_ocr_client):
    response = broken_ocr_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ocr"]["ready"] is False
    assert body["ocr"]["error_code"] == "ocr_init_failed"
    assert body["ocr"]["error"]


def test_health_never_leaks_server_paths(client):
    body = client.get("/api/health").text
    assert str(settings.data_dir) not in body
    assert "site-packages" not in body


# ---------------------------------------------------------------------------
# /api/ocr - success paths
# ---------------------------------------------------------------------------
def test_ocr_accepts_a_valid_png(client, sample_png, fake_ocr):
    response = client.post("/api/ocr", files=upload(sample_png, "invoice.png"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_type"] == "png"
    assert body["pages"] == 1
    assert body["char_count"] > 0
    assert "GLINT sample invoice" in body["text"]
    assert body["engine"] == fake_ocr.engine_label
    assert body["job_id"]
    assert fake_ocr.calls == 1


def test_ocr_returns_detected_patterns(client, sample_png):
    body = client.post("/api/ocr", files=upload(sample_png)).json()
    assert body["patterns"]["emails"] == ["accounts@glint.app"]
    assert body["patterns"]["dates"] == ["2026-10-10"]
    assert body["patterns"]["currency"] == ["$1,250.75"]


def test_ocr_processes_a_pdf_page_by_page(client, tmp_path, fake_ocr):
    pdf = make_pdf(tmp_path / "three.pdf", pages=3)
    response = client.post("/api/ocr", files=upload(pdf, "three.pdf"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_type"] == "pdf"
    assert body["pages"] == 3
    # One recognition call per page, sequential.
    assert fake_ocr.calls == 3


def test_ocr_persists_the_result(client, sample_png):
    body = client.post("/api/ocr", files=upload(sample_png)).json()
    job_id = body["job_id"]

    listing = client.get("/api/history").json()
    assert listing["count"] == 1
    assert listing["items"][0]["id"] == job_id
    assert "text" not in listing["items"][0]

    detail = client.get(f"/api/history/{job_id}").json()
    assert detail["text"] == body["text"]
    assert detail["char_count"] == body["char_count"]


def test_ocr_accepts_jpeg_and_webp(client, tmp_path, fake_ocr):
    # Pillow picks the container format from the extension, so both of these
    # are real JPEG / real WEBP files with the correct magic bytes.
    jpg = make_text_image(tmp_path / "scan.jpg")
    webp = make_text_image(tmp_path / "scan.webp")
    assert Path(jpg).read_bytes()[:3] == b"\xff\xd8\xff"
    assert Path(webp).read_bytes()[:4] == b"RIFF"

    assert client.post("/api/ocr", files=upload(jpg)).json()["file_type"] == "jpeg"
    assert client.post("/api/ocr", files=upload(webp)).json()["file_type"] == "webp"


def test_ocr_strips_directory_parts_from_the_filename(client, sample_png):
    body = client.post(
        "/api/ocr", files=upload(sample_png, "../../secret/invoice.png")
    ).json()
    assert body["filename"] == "invoice.png"
    assert "/" not in body["filename"]


# ---------------------------------------------------------------------------
# /api/ocr - failure paths
# ---------------------------------------------------------------------------
def test_ocr_rejects_an_unsupported_format(client, tmp_path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("just text, not a document image")
    response = client.post("/api/ocr", files=upload(text_file))
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "unsupported_format"
    assert "not supported" in body["error"]["message"].lower()


def test_ocr_rejects_a_disguised_file(client, tmp_path):
    # A text file renamed to .png must be rejected: content, not the name, wins.
    fake = tmp_path / "not-really.png"
    fake.write_bytes(b"this is definitely not a png image at all")
    response = client.post("/api/ocr", files=upload(fake))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_format"


def test_ocr_rejects_an_empty_file(client, tmp_path):
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    response = client.post("/api/ocr", files=upload(empty))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_ocr_rejects_an_oversized_file(client, tmp_path):
    big = tmp_path / "big.png"
    limit = settings.max_file_size_bytes
    with big.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(b"0" * (limit + 1024))
    response = client.post("/api/ocr", files=upload(big))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_ocr_rejects_a_corrupt_pdf(client, tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\nthis is not a real pdf body\n")
    response = client.post("/api/ocr", files=upload(broken))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "corrupt_document"


def test_ocr_rejects_a_corrupt_image(client, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage" * 200)
    response = client.post("/api/ocr", files=upload(broken))
    assert response.status_code == 400
    assert response.json()["error"]["code"] in {
        "corrupt_document",
        "unsupported_format",
    }


def test_ocr_rejects_a_pdf_with_too_many_pages(client, tmp_path):
    pdf = make_pdf(tmp_path / "many.pdf", pages=settings.max_pdf_pages + 1)
    response = client.post("/api/ocr", files=upload(pdf))
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "too_many_pages"
    assert body["error"]["details"]["max_pages"] == settings.max_pdf_pages


def test_ocr_rejects_an_encrypted_pdf(client, tmp_path):
    import pymupdf

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "secret")
    target = tmp_path / "locked.pdf"
    try:
        document.save(
            target,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PyMuPDF cannot write encrypted PDFs here: {exc}")
    finally:
        document.close()

    response = client.post("/api/ocr", files=upload(target))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "encrypted_pdf"


def test_ocr_reports_an_engine_failure_as_500(client, sample_png, app_state_ocr_error):
    response = client.post("/api/ocr", files=upload(sample_png))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "ocr_failed"


def test_ocr_returns_503_when_the_engine_is_unavailable(broken_ocr_client, tmp_path):
    png = make_text_image(tmp_path / "x.png")
    response = broken_ocr_client.post("/api/ocr", files=upload(png))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ocr_unavailable"


def test_ocr_handles_empty_recognition_output(client, sample_png):
    from app.main import app

    app.state.ocr = FakeOCRService(lines=[])
    response = client.post("/api/ocr", files=upload(sample_png))
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == ""
    assert body["char_count"] == 0
    assert body["patterns"] == {"emails": [], "dates": [], "currency": []}
    assert body["warnings"], "an empty result must explain itself"


def test_ocr_missing_file_field_is_a_422(client):
    response = client.post("/api/ocr")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_request"
    assert body["error"]["details"]["fields"]


def test_error_responses_never_leak_filesystem_paths(client, tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\ngarbage")
    response = client.post("/api/ocr", files=upload(broken))
    text = response.text
    assert "glint-upload-" not in text
    assert str(settings.data_dir) not in text
    assert "Traceback" not in text


# ---------------------------------------------------------------------------
# /api/history
# ---------------------------------------------------------------------------
def test_history_is_empty_at_first(client):
    body = client.get("/api/history").json()
    assert body == {"items": [], "count": 0, "search": None}


def test_history_search_by_filename(client, tmp_path):
    first = make_text_image(tmp_path / "alpha.png")
    second = make_text_image(tmp_path / "beta.png")
    client.post("/api/ocr", files=upload(first, "alpha-report.png"))
    client.post("/api/ocr", files=upload(second, "beta-invoice.png"))

    body = client.get("/api/history", params={"search": "alpha"}).json()
    assert body["count"] == 1
    assert body["items"][0]["filename"] == "alpha-report.png"
    assert body["search"] == "alpha"


def test_history_detail_404_for_unknown_id(client):
    response = client.get("/api/history/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_history_delete_one_entry(client, sample_png):
    job_id = client.post("/api/ocr", files=upload(sample_png)).json()["job_id"]

    response = client.delete(f"/api/history/{job_id}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "job_id": job_id}

    assert client.get(f"/api/history/{job_id}").status_code == 404
    assert client.delete(f"/api/history/{job_id}").status_code == 404


def test_history_clear(client, sample_png):
    client.post("/api/ocr", files=upload(sample_png))
    client.post("/api/ocr", files=upload(sample_png))
    assert client.get("/api/history").json()["count"] == 2

    response = client.delete("/api/history")
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 2
    assert client.get("/api/history").json()["count"] == 0


# ---------------------------------------------------------------------------
# /api/analytics
# ---------------------------------------------------------------------------
def test_analytics_with_no_records(client):
    body = client.get("/api/analytics").json()
    assert body["has_data"] is False
    assert body["total_documents"] == 0
    assert body["total_pages"] == 0
    assert body["average_duration_ms"] == 0.0
    assert body["most_common_file_type"] is None


def test_analytics_uses_real_stored_data(client, tmp_path):
    pdf = make_pdf(tmp_path / "doc.pdf", pages=2)
    png = make_text_image(tmp_path / "doc.png")
    client.post("/api/ocr", files=upload(pdf, "doc.pdf"))
    client.post("/api/ocr", files=upload(png, "doc.png"))
    client.post("/api/ocr", files=upload(png, "doc2.png"))

    body = client.get("/api/analytics").json()
    assert body["has_data"] is True
    assert body["total_documents"] == 3
    assert body["total_pages"] == 4  # 2 + 1 + 1
    assert body["average_duration_ms"] > 0
    assert body["most_common_file_type"] == "png"
    assert body["file_type_counts"] == {"png": 2, "pdf": 1}
    assert body["total_characters"] > 0


def test_analytics_chart_is_a_png_without_history(client):
    response = client.get("/api/analytics/chart")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_analytics_chart_is_a_png_with_history(client, sample_png):
    client.post("/api/ocr", files=upload(sample_png))
    response = client.get("/api/analytics/chart")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1000


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------
def test_unknown_route_uses_the_shared_error_shape(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}


def test_public_config_exposes_limits_without_secrets(client):
    body = client.get("/api/config").json()
    assert body["limits"]["max_pdf_pages"] == settings.max_pdf_pages
    assert "db" not in body
    assert str(settings.data_dir) not in str(body)


@pytest.fixture
def app_state_ocr_error(client):
    """Swap the engine for one that raises during recognition."""
    from app.main import app
    from app.ocr_service import OCRRunError

    app.state.ocr = FakeOCRService(raise_on_recognize=OCRRunError("boom"))
    yield app.state.ocr
