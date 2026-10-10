"""REAL local OCR integration tests.

These tests do not mock anything: they load the RapidOCR engine that ships with
the project (PP-OCRv6 "small" ONNX models bundled inside the ``rapidocr``
wheel) and run inference on the CPU.

They are marked ``integration`` and are skipped automatically when the OCR
package or its model files are not installed, so a plain ``pytest`` run on a
machine without the models still passes.

Run them explicitly with:

    cd backend
    ..\\.venv\\Scripts\\python -m pytest -m integration -v

Assertions are deliberately loose: the exact recognized string depends on the
model version, so we check that the run succeeded, that text came back and that
a few unambiguous words are present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("rapidocr", reason="RapidOCR is not installed")

from app.ocr_service import OCRService  # noqa: E402
from conftest import make_pdf, make_text_image  # noqa: E402


def _models_available() -> bool:
    """True when the bundled ONNX model files are present on this machine."""
    try:
        import rapidocr

        models = Path(rapidocr.__file__).resolve().parent / "models"
    except Exception:  # pragma: no cover
        return False
    return bool(list(models.glob("*.onnx")))


requires_models = pytest.mark.skipif(
    not _models_available(),
    reason="Bundled RapidOCR ONNX models are not available",
)

pytestmark = [pytest.mark.integration, requires_models]


@pytest.fixture(scope="module")
def engine() -> OCRService:
    """One real engine for the whole module (models are expensive to load)."""
    service = OCRService()
    assert service.initialize() is True, service.status()
    return service


def test_real_engine_reports_honest_status(engine: OCRService):
    status = engine.status()
    assert status["ready"] is True
    assert status["device"] == "cpu"
    assert status["runtime"] == "onnxruntime"
    assert status["runtime_version"]
    assert "PP-OCRv6" in status["model"]
    assert status["error"] is None


def test_real_ocr_reads_a_printed_image(engine: OCRService, tmp_path: Path):
    image_path = make_text_image(
        tmp_path / "invoice.png",
        lines=[
            "GLINT INVOICE",
            "Total due: $1,250.75",
            "Email: billing@glint.app",
        ],
        size=(1000, 380),
    )
    from PIL import Image

    image = Image.open(image_path)
    lines, elapsed = engine.recognize(image)
    image.close()

    joined = " ".join(lines).lower()
    assert lines, "a printed image must produce at least one line"
    assert "glint" in joined
    assert "invoice" in joined
    assert "1,250.75" in joined or "1250.75" in joined
    assert elapsed >= 0.0


def test_real_ocr_returns_empty_list_for_a_blank_page(engine: OCRService, tmp_path: Path):
    from PIL import Image

    blank = tmp_path / "blank.png"
    Image.new("RGB", (700, 500), "white").save(blank)
    image = Image.open(blank)
    lines, _ = engine.recognize(image)
    image.close()
    assert lines == []


def test_real_full_pipeline_over_the_api(tmp_path: Path):
    """End to end: upload a real PDF, run real OCR, store the real result."""
    from fastapi.testclient import TestClient

    from app import database
    from app.main import app

    database.init_db()
    database.clear_jobs()

    app.state.ocr = OCRService()
    pdf = make_pdf(tmp_path / "real.pdf", pages=2, text="GLINT quarterly report")

    with TestClient(app) as client:
        assert client.get("/api/health").json()["ocr"]["ready"] is True

        with pdf.open("rb") as handle:
            response = client.post(
                "/api/ocr",
                files={"file": ("real.pdf", handle, "application/pdf")},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pages"] == 2
        assert body["char_count"] > 0
        assert body["text"].strip()
        assert "glint" in body["text"].lower()
        assert "RapidOCR" in body["engine"]
        assert body["duration_ms"] > 0

        stored = client.get(f"/api/history/{body['job_id']}").json()
        assert stored["text"] == body["text"]
        # The contact line printed on every page should surface as a pattern.
        assert "hello@glint.app" in stored["patterns"]["emails"]
        assert "2026-10-10" in stored["patterns"]["dates"]

        analytics = client.get("/api/analytics").json()
        assert analytics["total_documents"] == 1
        assert analytics["total_pages"] == 2

        chart = client.get("/api/analytics/chart")
        assert chart.status_code == 200
        assert chart.content[:8] == b"\x89PNG\r\n\x1a\n"

    database.clear_jobs()
