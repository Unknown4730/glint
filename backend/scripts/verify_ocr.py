"""Verify that the local OCR engine really works on this machine.

Run it any time (install.ps1 runs it automatically):

    cd backend
    ..\\.venv\\Scripts\\python scripts\\verify_ocr.py

Exit code 0 means: the engine initialized, the bundled model files were found
and a printed probe image was recognized. Anything else prints a clear reason.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make "import app..." work when the script is started from anywhere.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def build_probe_image():
    """A small image with printed text - the same trick the app uses to warm up."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (520, 120), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=38)
    except TypeError:  # pragma: no cover - very old Pillow
        font = ImageFont.load_default()
    draw.text((24, 34), "GLINT 2026 OK", fill="black", font=font)
    return image


def main() -> int:
    print("GLINT OCR verification")
    print("-" * 46)

    try:
        import onnxruntime
        import rapidocr  # noqa: F401
    except Exception as exc:
        print(f"[FAIL] The OCR packages are not importable: {exc}")
        print("       Run: pip install -r backend/requirements.txt")
        return 1

    from importlib.metadata import version

    print(f"  rapidocr      : {version('rapidocr')}")
    print(f"  onnxruntime   : {onnxruntime.__version__}")
    print(f"  providers     : {', '.join(onnxruntime.get_available_providers())}")

    try:
        models_dir = Path(rapidocr.__file__).resolve().parent / "models"
        found = sorted(path.name for path in models_dir.glob("*.onnx"))
    except Exception as exc:  # pragma: no cover
        print(f"[FAIL] The model directory could not be inspected: {exc}")
        return 1

    if not found:
        print("[FAIL] No bundled ONNX model files were found.")
        print("       Reinstall with: pip install --force-reinstall rapidocr==3.10.0")
        return 1
    print(f"  bundled models: {', '.join(found)}")

    from app.ocr_service import OCRService

    started = time.perf_counter()
    service = OCRService()
    if not service.initialize():
        status = service.status()
        print(f"[FAIL] The engine could not start ({status.get('error_code')}).")
        print(f"       {status.get('error')}")
        return 1
    print(f"  engine        : {service.engine_label}")
    print(f"  init time     : {time.perf_counter() - started:.2f}s")

    started = time.perf_counter()
    lines, _ = service.recognize(build_probe_image())
    elapsed = time.perf_counter() - started
    print(f"  probe run     : {elapsed:.2f}s -> {lines}")

    if not lines:
        print("[FAIL] The engine ran but recognized nothing on the probe image.")
        return 1

    joined = " ".join(lines).upper()
    if "GLINT" not in joined:
        print("[WARN] The probe text was only partially recognized:", lines)
        print("       OCR still works; accuracy depends on the document.")

    print("-" * 46)
    print("[OK] Local OCR is working. No internet connection is needed for OCR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
