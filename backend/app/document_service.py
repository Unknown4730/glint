"""Document validation, image loading and page-by-page OCR.

The pipeline for one upload is:

1. Validate the file size and the *real* content type (magic bytes, not the
   filename and not the MIME type the browser claims).
2. For an image: verify it with Pillow, apply EXIF orientation, convert to RGB
   and downscale it if it is larger than the configured limit.
3. For a PDF: open it with PyMuPDF, refuse encrypted files, refuse documents
   with more pages than the configured limit and then render **one page at a
   time** so that only a single bitmap is in memory.
4. Hand each page to the OCR service and collect the recognized lines.

The original document is never stored: it lives in a temporary directory that
Python removes as soon as processing ends - including when an exception is
raised.

Concepts demonstrated: file handling, exceptions, loops, dictionaries,
Pillow/PyMuPDF usage and a small amount of NumPy-free image work.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import IMAGE_EXTENSIONS, Settings, settings
from .ocr_service import OCRService, ocr_service
from .text_utils import count_lines, normalize_text

logger = logging.getLogger("glint.documents")


# ---------------------------------------------------------------------------
# Errors - each one knows its own HTTP status and a short machine readable code
# ---------------------------------------------------------------------------
class DocumentError(Exception):
    """Base class for every "the user's document is not processable" error."""

    code = "document_error"
    status_code = 400

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EmptyFileError(DocumentError):
    code = "empty_file"
    status_code = 400


class FileTooLargeError(DocumentError):
    code = "file_too_large"
    status_code = 413


class UnsupportedFormatError(DocumentError):
    code = "unsupported_format"
    status_code = 400


class CorruptDocumentError(DocumentError):
    code = "corrupt_document"
    status_code = 400


class EncryptedPDFError(DocumentError):
    code = "encrypted_pdf"
    status_code = 400


class PageLimitError(DocumentError):
    code = "too_many_pages"
    status_code = 400


class EmptyDocumentError(DocumentError):
    code = "empty_document"
    status_code = 400


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class PageStat:
    """Cheap per-page metadata (no text) used for logging and debugging."""

    page: int
    characters: int
    duration_ms: float
    width: int
    height: int


@dataclass
class DocumentResult:
    """Everything the API needs to answer one OCR request."""

    filename: str
    file_type: str
    pages: int
    text: str
    char_count: int
    line_count: int
    duration_ms: float
    engine: str
    page_stats: List[PageStat] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "file_type": self.file_type,
            "pages": self.pages,
            "text": self.text,
            "char_count": self.char_count,
            "line_count": self.line_count,
            "duration_ms": self.duration_ms,
            "engine": self.engine,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def extension_of(filename: str) -> str:
    """Lower-cased file extension of a user supplied name (never a path)."""
    # Only the basename is used: a client cannot inject a directory this way.
    name = Path(filename or "").name
    return Path(name).suffix.lower()


def sniff_document_kind(data_head: bytes, filename: str) -> str:
    """Decide what the file really is from its first bytes.

    Returns ``"pdf"``, ``"png"``, ``"jpeg"``, ``"webp"`` or raises
    :class:`UnsupportedFormatError`.
    """
    if not data_head:
        raise EmptyFileError("The uploaded file is empty.")

    if data_head.startswith(b"%PDF-"):
        return "pdf"
    if data_head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data_head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data_head[:4] == b"RIFF" and data_head[8:12] == b"WEBP":
        return "webp"

    extension = extension_of(filename)
    allowed = ", ".join(sorted(IMAGE_EXTENSIONS | {".pdf"}))
    raise UnsupportedFormatError(
        "This file type is not supported by Glint. Supported formats: "
        f"{allowed}.",
        details={"extension": extension},
    )


def validate_size(size_bytes: int, config: Optional[Settings] = None) -> None:
    """Reject files that are bigger than the configured limit."""
    config = config or settings
    if size_bytes <= 0:
        raise EmptyFileError("The uploaded file is empty.")
    if size_bytes > config.max_file_size_bytes:
        raise FileTooLargeError(
            f"This file is {size_bytes / (1024 * 1024):.1f} MB. Glint accepts "
            f"documents up to {config.max_file_size_mb} MB.",
            details={
                "size_bytes": size_bytes,
                "max_bytes": config.max_file_size_bytes,
            },
        )


def safe_display_name(filename: str, fallback: str = "document") -> str:
    """A filename that is safe to store and show.

    Directory parts are stripped and control characters are removed, so an
    uploaded name can never be used to build a filesystem path.
    """
    raw = str(filename or "").strip()
    # Split on *both* separators so the result is identical on Windows and
    # POSIX, and so a client can never smuggle a directory into the name.
    for separator in ("/", "\\", chr(0)):
        raw = raw.split(separator)[-1]
    cleaned = "".join(ch for ch in raw if ch.isprintable()).strip()
    return cleaned[:180] or fallback


# ---------------------------------------------------------------------------
# Image handling
# ---------------------------------------------------------------------------
def load_image(path: Path, config: Optional[Settings] = None) -> Image.Image:
    """Open, verify and normalize one image file.

    Pillow's ``verify()`` catches truncated or corrupt files cheaply. Because
    ``verify()`` invalidates the image object, the file is opened a second time
    for real use - that is the documented Pillow behaviour.
    """
    config = config or settings

    try:
        with Image.open(path) as probe:
            probe.verify()
    except (UnidentifiedImageError, SyntaxError, OSError, ValueError) as exc:
        logger.warning("Image verification failed: %s", type(exc).__name__)
        raise CorruptDocumentError(
            "This image could not be read. It may be corrupted or truncated."
        ) from exc

    try:
        image = Image.open(path)
        image.load()
    except Exception as exc:
        logger.warning("Image could not be decoded: %s", type(exc).__name__)
        raise CorruptDocumentError(
            "This image could not be decoded. It may be corrupted."
        ) from exc

    try:
        image = ImageOps.exif_transpose(image) or image
    except Exception:  # pragma: no cover - EXIF data can be exotic
        pass

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    width, height = image.size
    if width <= 0 or height <= 0:
        raise CorruptDocumentError("This image has no pixels.")

    longest = max(width, height)
    if longest > config.max_image_side_px:
        scale = config.max_image_side_px / float(longest)
        new_size = (
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale))),
        )
        # ``resize`` on the same object keeps memory low; aspect ratio is kept.
        image = image.resize(new_size, Image.LANCZOS)
        logger.info(
            "Image downscaled from %dx%d to %dx%d", width, height, *new_size
        )
    return image



# ---------------------------------------------------------------------------
# A small NumPy based image check
# ---------------------------------------------------------------------------
def brightness_stats(image: Image.Image) -> Dict[str, float]:
    """Mean brightness and contrast of a page, computed on a tiny thumbnail.

    This is the one place where NumPy is genuinely useful: it turns the pixel
    buffer into an array so that the mean and the standard deviation can be
    computed in a single pass over a *small* copy of the image (128 px), which
    costs no measurable memory even on an 8 GB machine.

    The numbers are only used to warn the user about scans that are very likely
    to produce a poor OCR result (nearly black or nearly blank pages).
    """
    try:
        probe = image.copy()
        probe.thumbnail((128, 128))
        array = np.asarray(probe.convert("L"), dtype=np.uint8)
        probe.close()
        if array.size == 0:
            return {"mean": 0.0, "std": 0.0}
        return {
            "mean": round(float(array.mean()), 1),
            "std": round(float(array.std()), 1),
        }
    except Exception:  # pragma: no cover - never fail because of a statistic
        logger.debug("Brightness statistics could not be computed")
        return {"mean": 0.0, "std": 0.0}


def brightness_warning(stats: Dict[str, float]) -> Optional[str]:
    """Return a user facing warning for suspicious pages, or ``None``."""
    mean = stats.get("mean", 0.0)
    std = stats.get("std", 0.0)
    if mean < 45:
        return (
            "This page is very dark. OCR works best on dark text over a light "
            "background, so the result may be incomplete."
        )
    if mean >= 250 and std < 5:
        return (
            "This page looks almost completely blank. If it does contain text, "
            "the contrast may be too low to recognize."
        )
    return None


# ---------------------------------------------------------------------------
# PDF handling
# ---------------------------------------------------------------------------
def iter_pdf_pages(path: Path, config: Optional[Settings] = None):
    """Yield ``(page_number, PIL image)`` for each page, one at a time.

    This is a generator on purpose: only the page that is currently being
    recognized exists in memory.
    """
    config = config or settings

    try:
        import pymupdf
    except Exception as exc:  # pragma: no cover - depends on install
        raise CorruptDocumentError(
            "PDF support is not installed on this machine."
        ) from exc

    try:
        document = pymupdf.open(path)
    except Exception as exc:
        logger.warning("PyMuPDF could not open the file: %s", type(exc).__name__)
        raise CorruptDocumentError(
            "This PDF could not be opened. It may be corrupted or not a real "
            "PDF file."
        ) from exc

    try:
        if document.needs_pass or document.is_encrypted:
            raise EncryptedPDFError(
                "This PDF is password protected. Glint does not open encrypted "
                "documents - please remove the password and try again."
            )

        page_count = document.page_count
        if page_count == 0:
            raise EmptyDocumentError("This PDF has no pages.")
        if page_count > config.max_pdf_pages:
            raise PageLimitError(
                f"This PDF has {page_count} pages. Glint processes up to "
                f"{config.max_pdf_pages} pages per document.",
                details={"pages": page_count, "max_pages": config.max_pdf_pages},
            )

        zoom = config.pdf_render_dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)

        for index in range(page_count):
            try:
                page = document.load_page(index)
                pixmap = page.get_pixmap(
                    matrix=matrix, alpha=False, colorspace=pymupdf.csRGB
                )
                image = Image.frombytes(
                    "RGB", (pixmap.width, pixmap.height), pixmap.samples
                )
            except Exception as exc:
                logger.warning("Page %s could not be rendered", index + 1)
                raise CorruptDocumentError(
                    f"Page {index + 1} of this PDF could not be rendered. The "
                    "file may be damaged."
                ) from exc
            finally:
                # Release the bitmap as early as possible.
                pixmap = None  # type: ignore[assignment]

            longest = max(image.size)
            if longest > config.max_image_side_px:
                image.thumbnail(
                    (config.max_image_side_px, config.max_image_side_px),
                    Image.LANCZOS,
                )

            yield index + 1, image

            image.close()
            try:
                page.cleanup()
            except Exception:  # pragma: no cover
                pass
    finally:
        document.close()


# ---------------------------------------------------------------------------
# The main entry point
# ---------------------------------------------------------------------------
def process_document(
    path: Path,
    *,
    filename: str,
    size_bytes: int,
    kind: str,
    config: Optional[Settings] = None,
    engine: Optional[OCRService] = None,
) -> DocumentResult:
    """Run OCR over one already-saved upload and return the result."""
    config = config or settings
    engine = engine or ocr_service

    validate_size(size_bytes, config)
    display_name = safe_display_name(filename)

    started = time.perf_counter()
    page_texts: List[str] = []
    page_stats: List[PageStat] = []
    warnings: List[str] = []

    if kind == "pdf":
        for page_number, image in iter_pdf_pages(path, config):
            page_started = time.perf_counter()
            note = brightness_warning(brightness_stats(image))
            if note and note not in warnings:
                warnings.append(note)
            lines, _engine_seconds = engine.recognize(image)
            text = normalize_text(lines)
            width, height = image.size
            image.close()
            page_texts.append(text)
            page_stats.append(
                PageStat(
                    page=page_number,
                    characters=len(text),
                    duration_ms=round(
                        (time.perf_counter() - page_started) * 1000.0, 1
                    ),
                    width=width,
                    height=height,
                )
            )
            logger.info(
                "Page %s recognized: %s characters", page_number, len(text)
            )
        pages = len(page_stats)
        file_type = "pdf"
    else:
        image = load_image(path, config)
        stats = brightness_stats(image)
        note = brightness_warning(stats)
        if note:
            warnings.append(note)
        page_started = time.perf_counter()
        lines, _engine_seconds = engine.recognize(image)
        text = normalize_text(lines)
        width, height = image.size
        image.close()
        page_texts.append(text)
        page_stats.append(
            PageStat(
                page=1,
                characters=len(text),
                duration_ms=round((time.perf_counter() - page_started) * 1000.0, 1),
                width=width,
                height=height,
            )
        )
        pages = 1
        file_type = kind

    full_text = normalize_text([block for block in page_texts if block])
    duration_ms = round((time.perf_counter() - started) * 1000.0, 1)

    if not full_text.strip():
        warnings.append(
            "No text could be recognized in this document. Scanned images with "
            "very low contrast, handwriting or unusual layouts may produce an "
            "empty result."
        )
    if pages > 1:
        empty_pages = [
            stat.page for stat in page_stats if stat.characters == 0
        ]
        if empty_pages:
            warnings.append(
                "No text was found on page(s): "
                + ", ".join(str(number) for number in empty_pages)
                + "."
            )

    logger.info(
        "Processed %s (%s, %s page(s)) in %.0f ms -> %s characters",
        display_name,
        file_type,
        pages,
        duration_ms,
        len(full_text),
    )

    return DocumentResult(
        filename=display_name,
        file_type=file_type,
        pages=pages,
        text=full_text,
        char_count=len(full_text),
        line_count=count_lines(full_text),
        duration_ms=duration_ms,
        engine=engine.engine_label,
        page_stats=page_stats,
        warnings=warnings,
    )
