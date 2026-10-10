"""The OCR engine wrapper.

Glint uses **RapidOCR 3.10** with the **ONNX Runtime CPU** execution provider.
The PP-OCRv6 "small" detection/recognition models and the PP-OCRv4 mobile
orientation classifier are bundled inside the installed ``rapidocr`` wheel, so
after ``pip install`` no model download is needed and OCR runs completely
offline on the CPU.

The class below is the only place in Glint that talks to the OCR library:

* the engine is created once and reused (model weights are not reloaded per
  request),
* a lock guarantees that only one document is recognized at a time, which is
  what an 8 GB machine wants,
* every failure is turned into a small, safe message - the raw exception (which
  may contain local filesystem paths) is only written to the server log.

Concepts demonstrated: a small class, lazy initialization, threading locks,
exception handling and logging.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .config import Settings, settings

logger = logging.getLogger("glint.ocr")


def _library_version() -> Optional[str]:
    """Installed RapidOCR version, or ``None`` if it cannot be determined."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("rapidocr")
    except PackageNotFoundError:  # pragma: no cover
        return None


class OCRServiceError(Exception):
    """Base class for OCR problems."""

    code = "ocr_error"
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class OCRNotReadyError(OCRServiceError):
    """The engine could not be initialized (missing package or model file)."""

    code = "ocr_unavailable"
    status_code = 503


class OCRRunError(OCRServiceError):
    """The engine was ready but recognition of this image failed."""

    code = "ocr_failed"
    status_code = 500


class OCRService:
    """A very small object-oriented wrapper around RapidOCR."""
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self._engine: Any = None
        self._run_lock = threading.Lock()
        self._init_lock = threading.Lock()
        self._error_code: Optional[str] = None
        self._error_hint: Optional[str] = None
        self._runtime_version: Optional[str] = None
        self._library_version: Optional[str] = None
        self._warm: bool = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        """Create the OCR engine once. Returns ``True`` when it is usable."""
        if self._engine is not None:
            return True

        with self._init_lock:
            if self._engine is not None:
                return True
            try:
                import rapidocr  # noqa: F401  (import check only)
                from rapidocr import RapidOCR
            except Exception as exc:  # pragma: no cover - depends on install
                logger.exception("RapidOCR could not be imported")
                self._set_error("ocr_missing_package", exc)
                return False

            try:
                self._library_version = _library_version()
                self._engine = RapidOCR(params=self._engine_params())
                self._runtime_version = self._read_onnxruntime_version()
                self._error_code = None
                self._error_hint = None
                logger.info(
                    "RapidOCR engine initialized (rapidocr=%s, onnxruntime=%s)",
                    self._library_version,
                    self._runtime_version,
                )
            except Exception as exc:
                logger.exception("RapidOCR engine initialization failed")
                self._engine = None
                self._set_error("ocr_init_failed", exc)
                return False

        if self.config.ocr_warmup:
            self.warm_up()
        return True

    def _engine_params(self) -> Dict[str, Any]:
        """RapidOCR parameters. Dotted keys are the library's own convention.

        Model *selection* is only overridden when the user asked for a model
        type that RapidOCR really supports; otherwise the bundled defaults are
        used untouched.
        """
        params: Dict[str, Any] = {
            "Global.log_level": self.config.ocr_log_level,
            "Global.max_side_len": self.config.ocr_max_side_len,
            "Global.use_cls": self.config.ocr_use_cls,
            "Det.limit_side_len": self.config.ocr_det_limit_side_len,
        }
        if self.config.ocr_threads > 0:
            params["EngineConfig.onnxruntime.intra_op_num_threads"] = (
                self.config.ocr_threads
            )
            params["EngineConfig.onnxruntime.inter_op_num_threads"] = 1

        if self.config.ocr_model_type != "small":
            # "tiny"/"medium" are real RapidOCR model types but they are not
            # bundled in the wheel, so they are downloaded once on first use.
            try:
                from rapidocr import ModelType

                params["Det.model_type"] = ModelType(self.config.ocr_model_type)
                params["Rec.model_type"] = ModelType(self.config.ocr_model_type)
                logger.warning(
                    "Non-default OCR model type '%s' requested; RapidOCR may "
                    "download it on first use.",
                    self.config.ocr_model_type,
                )
            except Exception as exc:  # pragma: no cover - depends on version
                logger.warning("Could not apply model type override: %s", exc)

        return params

    @staticmethod
    def _read_onnxruntime_version() -> Optional[str]:
        try:
            import onnxruntime

            return onnxruntime.__version__
        except Exception:  # pragma: no cover
            return None

    def _set_error(self, code: str, exc: Exception) -> None:
        """Store a *safe* error description (never a local path or traceback)."""
        self._error_code = code
        if isinstance(exc, ModuleNotFoundError):
            self._error_hint = (
                "The OCR package is not installed. Run install.ps1 (or "
                "`pip install -r backend/requirements.txt`) again."
            )
        elif code == "ocr_init_failed":
            self._error_hint = (
                "The local OCR engine could not start. Re-run install.ps1; if "
                "you changed GLINT_OCR_MODEL_TYPE, switch it back to 'small'."
            )
        else:
            self._error_hint = "The local OCR engine is unavailable."

    def warm_up(self) -> bool:
        """Force the model files to load with a tiny throw-away image.

        RapidOCR loads det/cls/rec lazily on the first call. Warming up at
        start-up means ``/api/health`` reports the truth and the user's first
        document is not slowed down by model loading.
        """
        if self._engine is None:
            return False
        if self._warm:
            return True
        try:
            from PIL import Image, ImageDraw, ImageFont

            probe = Image.new("RGB", (360, 90), "white")
            draw = ImageDraw.Draw(probe)
            try:
                font = ImageFont.load_default(size=34)
            except TypeError:  # very old Pillow versions
                font = ImageFont.load_default()
            draw.text((16, 24), "Glint OCR 2026", fill="black", font=font)
            started = time.perf_counter()
            with self._run_lock:
                self._engine(probe)
            self._warm = True
            logger.info(
                "OCR warm-up finished in %.2fs", time.perf_counter() - started
            )
        except Exception:
            logger.exception("OCR warm-up failed (engine stays usable)")
        return self._warm

    # ------------------------------------------------------------------
    # Recognition
    # ------------------------------------------------------------------
    def recognize(self, image: Any) -> Tuple[List[str], float]:
        """Recognize text in one PIL image.

        Returns ``(lines, seconds_reported_by_engine)``. An image without any
        recognizable text returns an empty list - that is a valid result, not
        an error.
        """
        if self._engine is None and not self.initialize():
            raise OCRNotReadyError(self._error_hint or "OCR is not available.")

        try:
            with self._run_lock:  # one document at a time, sequential pages
                output = self._engine(image)
        except OCRServiceError:
            raise
        except Exception as exc:
            logger.exception("OCR recognition failed")
            raise OCRRunError(
                "The OCR engine could not read this page."
            ) from exc

        raw_lines = getattr(output, "txts", None) or []
        lines = [str(line) for line in raw_lines if str(line).strip()]
        elapsed = getattr(output, "elapse", None)
        try:
            elapsed = float(elapsed) if elapsed is not None else 0.0
        except (TypeError, ValueError):
            elapsed = 0.0

        # The engine keeps a copy of the decoded image; drop our reference so
        # the memory can be freed before the next page is rendered.
        del output
        return lines, elapsed

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    @property
    def is_ready(self) -> bool:
        return self._engine is not None

    @property
    def engine_label(self) -> str:
        """Name stored with every job and shown in the UI."""
        version = f" {self._library_version}" if self._library_version else ""
        return f"RapidOCR{version} - {self.config.ocr_profile_label}"

    def status(self) -> Dict[str, Any]:
        """Honest readiness information for ``GET /api/health``."""
        return {
            "ready": self.is_ready,
            "engine": "rapidocr",
            "engine_version": self._library_version,
            "runtime": "onnxruntime",
            "runtime_version": self._runtime_version,
            "model": self.config.ocr_profile_label,
            "device": "cpu",
            "error_code": self._error_code,
            "error": self._error_hint,
        }


# One shared service for the whole process (the engine is expensive to build).
ocr_service = OCRService()
