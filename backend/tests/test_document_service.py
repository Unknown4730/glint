"""Unit tests for validation, sniffing, image loading and the NumPy check."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.config import Settings
from app.document_service import (
    CorruptDocumentError,
    EmptyFileError,
    FileTooLargeError,
    PageLimitError,
    UnsupportedFormatError,
    brightness_stats,
    brightness_warning,
    extension_of,
    iter_pdf_pages,
    load_image,
    safe_display_name,
    sniff_document_kind,
    validate_size,
)
from conftest import make_pdf, make_text_image


# ---------------------------------------------------------------------------
# Names and extensions
# ---------------------------------------------------------------------------
def test_extension_of_is_case_insensitive():
    assert extension_of("Report.PDF") == ".pdf"
    assert extension_of("photo.JPG") == ".jpg"
    assert extension_of("no-extension") == ""


def test_safe_display_name_removes_path_traversal():
    assert safe_display_name("../../etc/passwd") == "passwd"
    assert safe_display_name("C:\\Users\\me\\invoice.pdf") == "invoice.pdf"
    assert safe_display_name("   ") == "document"
    assert safe_display_name("normal name.png") == "normal name.png"


def test_safe_display_name_truncates_absurd_names():
    assert len(safe_display_name("a" * 500 + ".pdf")) == 180


# ---------------------------------------------------------------------------
# Content sniffing
# ---------------------------------------------------------------------------
def test_sniff_detects_pdf_png_jpeg_webp():
    assert sniff_document_kind(b"%PDF-1.7\n...", "x") == "pdf"
    assert sniff_document_kind(b"\x89PNG\r\n\x1a\n....", "x") == "png"
    assert sniff_document_kind(b"\xff\xd8\xff\xe0....", "x") == "jpeg"
    assert sniff_document_kind(b"RIFF\x00\x00\x00\x00WEBP", "x") == "webp"


def test_sniff_rejects_unknown_content():
    with pytest.raises(UnsupportedFormatError) as info:
        sniff_document_kind(b"GIF89a not supported here", "image.gif")
    assert info.value.status_code == 400
    assert info.value.code == "unsupported_format"


def test_sniff_rejects_empty_content():
    with pytest.raises(EmptyFileError):
        sniff_document_kind(b"", "empty.png")


def test_sniff_ignores_a_lying_filename():
    # The bytes win over the extension, so a text file named .pdf is rejected.
    with pytest.raises(UnsupportedFormatError):
        sniff_document_kind(b"plain text content", "important.pdf")


# ---------------------------------------------------------------------------
# Size validation
# ---------------------------------------------------------------------------
def test_validate_size_accepts_files_below_the_limit():
    validate_size(1024)  # must not raise


def test_validate_size_rejects_zero_bytes():
    with pytest.raises(EmptyFileError):
        validate_size(0)


def test_validate_size_rejects_oversized_files_with_details():
    config = Settings(max_file_size_mb=1)
    with pytest.raises(FileTooLargeError) as info:
        validate_size(2 * 1024 * 1024, config)
    assert info.value.status_code == 413
    assert info.value.details["max_bytes"] == 1024 * 1024


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------
def test_load_image_returns_an_rgb_image(tmp_path: Path):
    path = make_text_image(tmp_path / "ok.png")
    image = load_image(path)
    assert image.mode in ("RGB", "L")
    assert image.size[0] > 0
    image.close()


def test_load_image_downscales_huge_images(tmp_path: Path):
    path = tmp_path / "huge.png"
    Image.new("RGB", (4200, 2100), "white").save(path)
    config = Settings(max_image_side_px=1000)
    image = load_image(path, config)
    assert max(image.size) == 1000
    # Aspect ratio is preserved.
    assert image.size == (1000, 500)
    image.close()


def test_load_image_keeps_small_images_untouched(tmp_path: Path):
    path = tmp_path / "small.png"
    Image.new("RGB", (400, 200), "white").save(path)
    image = load_image(path)
    assert image.size == (400, 200)
    image.close()


def test_load_image_rejects_corrupt_bytes(tmp_path: Path):
    path = tmp_path / "corrupt.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"nonsense" * 50)
    with pytest.raises(CorruptDocumentError):
        load_image(path)


def test_load_image_handles_transparent_png(tmp_path: Path):
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (300, 150), (255, 255, 255, 0)).save(path)
    image = load_image(path)
    assert image.mode == "RGB"
    image.close()


def test_load_image_applies_exif_orientation(tmp_path: Path):
    """A photo tagged "rotate 90" must come back already rotated."""
    path = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (200, 100), "white")
    exif = image.getexif()
    exif[0x0112] = 6  # EXIF Orientation tag: rotate 270 CW
    image.save(path, exif=exif.tobytes())
    image.close()

    loaded = load_image(path)
    assert loaded.size == (100, 200)
    loaded.close()


# ---------------------------------------------------------------------------
# PDF page iteration
# ---------------------------------------------------------------------------
def test_iter_pdf_pages_yields_one_page_at_a_time(tmp_path: Path):
    pdf = make_pdf(tmp_path / "doc.pdf", pages=3)
    seen = []
    for number, image in iter_pdf_pages(pdf):
        seen.append(number)
        assert isinstance(image, Image.Image)
        assert image.size[0] > 100
        image.close()
    assert seen == [1, 2, 3]


def test_iter_pdf_pages_rejects_documents_over_the_limit(tmp_path: Path):
    pdf = make_pdf(tmp_path / "long.pdf", pages=4)
    config = Settings(max_pdf_pages=2)
    with pytest.raises(PageLimitError):
        list(iter_pdf_pages(pdf, config))


def test_iter_pdf_pages_rejects_broken_files(tmp_path: Path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\nbroken body\n")
    with pytest.raises(CorruptDocumentError):
        list(iter_pdf_pages(broken))


def test_pdf_render_resolution_follows_the_dpi_setting(tmp_path: Path):
    pdf = make_pdf(tmp_path / "a4.pdf", pages=1)
    low = list(iter_pdf_pages(pdf, Settings(pdf_render_dpi=72)))[0][1]
    high = list(iter_pdf_pages(pdf, Settings(pdf_render_dpi=150)))[0][1]
    assert high.size[0] > low.size[0]
    low.close()
    high.close()


# ---------------------------------------------------------------------------
# The NumPy brightness check
# ---------------------------------------------------------------------------
def test_brightness_stats_of_a_white_page():
    image = Image.new("RGB", (300, 200), "white")
    stats = brightness_stats(image)
    assert stats["mean"] > 240
    assert brightness_warning(stats) is not None  # nearly blank


def test_brightness_stats_of_a_text_page(tmp_path: Path):
    image = Image.open(make_text_image(tmp_path / "text.png"))
    stats = brightness_stats(image)
    # A normal page of printed text has visible contrast and must not be
    # mistaken for a blank page.
    assert stats["std"] > 5
    assert brightness_warning(stats) is None


def test_brightness_warning_for_a_dark_page():
    image = Image.new("RGB", (300, 200), (10, 10, 10))
    assert brightness_warning(brightness_stats(image)) is not None


def test_brightness_stats_never_raises_on_a_broken_image():
    class NotAnImage:
        def copy(self):
            raise RuntimeError("nope")

    assert brightness_stats(NotAnImage()) == {"mean": 0.0, "std": 0.0}
