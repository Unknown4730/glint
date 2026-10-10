"""Shared pytest fixtures for the Glint backend.

The important idea: **no OCR model is downloaded or loaded for the fast tests**.
A ``FakeOCRService`` stands in for RapidOCR, so the API, validation, database
and analytics paths can all be tested in well under a second.

The real engine is exercised separately in ``test_real_ocr.py`` (marked
``integration``), which is skipped automatically when RapidOCR or its bundled
model files are unavailable.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

# Make ``import app...`` work when pytest is started from anywhere.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Point Glint at a throw-away data directory *before* the settings are read.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="glint-pytest-data-"))
os.environ.setdefault("GLINT_DATA_DIR", str(_TEST_DATA_DIR))
os.environ.setdefault("GLINT_OCR_WARMUP", "0")
os.environ.setdefault("GLINT_DB_FILENAME", "glint-test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app import database  # noqa: E402
from app.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Sample document generators
# ---------------------------------------------------------------------------
def make_text_image(
    path: Path,
    lines: Optional[List[str]] = None,
    size: tuple = (900, 320),
    background: str = "white",
    fill: str = "black",
    font_size: int = 36,
) -> Path:
    """Draw a simple PNG with printed text - enough for a real OCR smoke test."""
    lines = lines or ["GLINT test document", "Total: $250.00"]
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    y = 40
    for line in lines:
        draw.text((40, y), line, font=font, fill=fill)
        y += font_size + 24
    image.save(path)
    image.close()
    return path


def make_pdf(path: Path, pages: int = 2, text: str = "GLINT invoice page") -> Path:
    """Create a real PDF with PyMuPDF so the rendering path can be tested."""
    import pymupdf

    document = pymupdf.open()
    for index in range(pages):
        page = document.new_page(width=595, height=842)  # A4 in points
        page.insert_text(
            (72, 120),
            f"{text} {index + 1}",
            fontsize=24,
            fontname="helv",
            color=(0, 0, 0),
        )
        page.insert_text(
            (72, 170),
            "Contact: hello@glint.app   Date: 2026-10-10   Due: $1,250.75",
            fontsize=14,
            fontname="helv",
            color=(0, 0, 0),
        )
    document.save(path)
    document.close()
    return path


@pytest.fixture
def sample_png(tmp_path: Path) -> Path:
    return make_text_image(tmp_path / "sample.png")


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return make_pdf(tmp_path / "sample.pdf", pages=2)


# ---------------------------------------------------------------------------
# A stand-in OCR engine with the same surface as app.ocr_service.OCRService
# ---------------------------------------------------------------------------
class FakeOCRService:
    """Pretends to be the OCR service without loading any model."""

    def __init__(
        self,
        lines: Optional[List[str]] = None,
        ready: bool = True,
        raise_on_recognize: Optional[Exception] = None,
    ):
        self.lines = (
            lines
            if lines is not None
            else [
                "GLINT sample invoice",
                "Total due: $1,250.75",
                "Email: accounts@glint.app",
                "Issued: 2026-10-10",
            ]
        )
        self._ready = ready
        self._raise = raise_on_recognize
        self.calls = 0
        self.initialized = False

    # -- lifecycle -------------------------------------------------------
    def initialize(self) -> bool:
        self.initialized = True
        return self._ready

    def warm_up(self) -> bool:
        return self._ready

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def engine_label(self) -> str:
        return "FakeOCR - test profile (ONNX Runtime, CPU)"

    def status(self) -> dict:
        if self._ready:
            return {
                "ready": True,
                "engine": "rapidocr",
                "engine_version": "test",
                "runtime": "onnxruntime",
                "runtime_version": "test",
                "model": "test profile",
                "device": "cpu",
                "error_code": None,
                "error": None,
            }
        return {
            "ready": False,
            "engine": "rapidocr",
            "engine_version": None,
            "runtime": "onnxruntime",
            "runtime_version": None,
            "model": "test profile",
            "device": "cpu",
            "error_code": "ocr_init_failed",
            "error": "The local OCR engine could not start (test stub).",
        }

    # -- recognition -----------------------------------------------------
    def recognize(self, image):
        self.calls += 1
        if self._raise is not None:
            raise self._raise
        return list(self.lines), 0.05


@pytest.fixture
def fake_ocr() -> FakeOCRService:
    return FakeOCRService()


@pytest.fixture(autouse=True)
def clean_database():
    """Every test starts and ends with an empty history table."""
    database.init_db()
    database.clear_jobs()
    yield
    database.clear_jobs()


@pytest.fixture
def client(fake_ocr: FakeOCRService):
    """A TestClient whose OCR engine is the fake one."""
    app.state.ocr = fake_ocr
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def broken_ocr_client():
    """A TestClient whose OCR engine failed to initialize."""
    app.state.ocr = FakeOCRService(ready=False)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def upload(path: Path, filename: Optional[str] = None, content_type: str = ""):
    """Build the ``files`` argument for TestClient.post."""
    name = filename or path.name
    return {
        "file": (
            name,
            path.read_bytes(),
            content_type or "application/octet-stream",
        )
    }
