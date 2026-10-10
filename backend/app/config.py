"""Central configuration for the Glint backend.

Every limit, path and tunable used by Glint lives in this one file so that the
application can be adapted to a different machine without hunting through the
code base.

Values are read from environment variables (prefix ``GLINT_``) and fall back to
conservative defaults that suit the reference machine:

    Intel Core i5-7300HQ / 8 GB RAM / no dedicated GPU / Windows 10-11

Concepts demonstrated: functions, conditions, dictionaries, a frozen dataclass,
environment handling and path handling with ``pathlib``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# backend/app/config.py -> backend/app -> backend -> project root
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

MEGABYTE = 1024 * 1024


def env_str(name: str, default: str) -> str:
    """Return an environment variable as a string, or the default value."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def env_int(name: str, default: int) -> int:
    """Return an environment variable as an int, or the default value.

    An invalid value is never fatal: Glint logs nothing here and simply keeps
    the safe default instead.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    """Return an environment variable as a float, or the default value."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    """Return an environment variable as a bool ("1", "true", "yes", "on")."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: List[str]) -> List[str]:
    """Return a comma separated environment variable as a list of strings."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default)
    items = [part.strip() for part in raw.split(",")]
    return [part for part in items if part]


@dataclass(frozen=True)
class Settings:
    """All runtime settings for Glint, resolved once at start-up."""

    # --- identity ---------------------------------------------------------
    app_name: str = "GLINT"
    tagline: str = "See beyond the page."
    version: str = "1.0.0"

    # --- server -----------------------------------------------------------
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    cors_origins: List[str] = field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    serve_frontend: bool = True

    # --- document limits (the "conservative defaults" from the spec) -------
    max_file_size_mb: int = 10
    max_pdf_pages: int = 10
    max_image_side_px: int = 3000
    pdf_render_dpi: int = 150

    # --- OCR --------------------------------------------------------------
    # RapidOCR 3.10 ships PP-OCRv6 "small" det/rec ONNX models plus the
    # PP-OCRv4 mobile classifier inside the wheel, so nothing is downloaded
    # for the default profile.
    ocr_model_type: str = "small"
    ocr_lang: str = "ch"  # bundled multilingual model (Latin + Chinese)
    ocr_max_side_len: int = 2000
    ocr_det_limit_side_len: int = 736
    ocr_use_cls: bool = True
    ocr_threads: int = 0  # 0 = keep the RapidOCR default
    ocr_log_level: str = "error"
    ocr_warmup: bool = True

    # --- storage ----------------------------------------------------------
    data_dir: Path = BACKEND_DIR / "data"
    db_filename: str = "glint.db"
    history_page_size: int = 50

    # ------------------------------------------------------------------
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * MEGABYTE

    @property
    def db_path(self) -> Path:
        return Path(self.data_dir) / self.db_filename

    @property
    def ocr_profile_label(self) -> str:
        """Human readable description of the single OCR profile Glint uses."""
        return f"PP-OCRv6 {self.ocr_model_type} (ONNX Runtime, CPU)"

    def public_limits(self) -> dict:
        """Limits that are safe to show in the UI (no filesystem paths)."""
        return {
            "max_file_size_mb": self.max_file_size_mb,
            "max_pdf_pages": self.max_pdf_pages,
            "max_image_side_px": self.max_image_side_px,
            "pdf_render_dpi": self.pdf_render_dpi,
            "accepted_extensions": sorted(ACCEPTED_EXTENSIONS),
        }


ACCEPTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def load_settings() -> Settings:
    """Build a :class:`Settings` object from the environment.

    This is deliberately a plain function (not a framework feature) so that it
    stays readable and easy to explain.
    """
    data_dir = Path(env_str("GLINT_DATA_DIR", str(BACKEND_DIR / "data")))

    model_type = env_str("GLINT_OCR_MODEL_TYPE", "small").lower()
    if model_type not in {"tiny", "small", "medium"}:
        # Never advertise a model that is not supported by RapidOCR.
        model_type = "small"

    settings = Settings(
        backend_host=env_str("GLINT_BACKEND_HOST", "127.0.0.1"),
        backend_port=env_int("GLINT_BACKEND_PORT", 8000),
        frontend_origin=env_str("GLINT_FRONTEND_ORIGIN", "http://localhost:5173"),
        cors_origins=env_list(
            "GLINT_CORS_ORIGINS",
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        ),
        serve_frontend=env_bool("GLINT_SERVE_FRONTEND", True),
        max_file_size_mb=max(1, env_int("GLINT_MAX_FILE_SIZE_MB", 10)),
        max_pdf_pages=max(1, env_int("GLINT_MAX_PDF_PAGES", 10)),
        max_image_side_px=max(320, env_int("GLINT_MAX_IMAGE_SIDE_PX", 3000)),
        pdf_render_dpi=min(300, max(72, env_int("GLINT_PDF_RENDER_DPI", 150))),
        ocr_model_type=model_type,
        ocr_lang=env_str("GLINT_OCR_LANG", "ch"),
        ocr_max_side_len=max(320, env_int("GLINT_OCR_MAX_SIDE_LEN", 2000)),
        ocr_use_cls=env_bool("GLINT_OCR_USE_CLS", True),
        ocr_threads=env_int("GLINT_OCR_THREADS", 0),
        ocr_warmup=env_bool("GLINT_OCR_WARMUP", True),
        data_dir=data_dir,
        db_filename=env_str("GLINT_DB_FILENAME", "glint.db"),
        history_page_size=min(200, max(5, env_int("GLINT_HISTORY_PAGE_SIZE", 50))),
    )
    return settings


# One shared, immutable settings object for the whole process.
settings = load_settings()
