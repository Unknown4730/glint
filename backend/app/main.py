"""Glint backend - a small FastAPI application.

Design rules that were followed here on purpose:

* Route functions that touch the OCR engine are **synchronous** (``def``), so
  FastAPI runs them in a thread pool and the async event loop is never blocked
  by CPU-bound inference.
* A single lock inside :class:`OCRService` makes sure only one document is
  processed at a time - the right behaviour for an 8 GB machine.
* Every error leaves the backend in one JSON shape:
  ``{"error": {"code": ..., "message": ..., "details": {...}}}``.
* Raw tracebacks and local filesystem paths are logged on the server but never
  returned to the browser.
* Uploads are written to a temporary directory that is removed as soon as the
  request ends - successfully or not. The original document is never kept.

Concepts demonstrated: FastAPI routing, dependency injection, exception
handling, context managers, logging and structured responses.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import database
from .analytics_service import compute_summary, render_chart_png
from .config import MEGABYTE, PROJECT_ROOT, settings
from .document_service import (
    DocumentError,
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFormatError,
    process_document,
    sniff_document_kind,
)
from .ocr_service import (
    OCRNotReadyError,
    OCRService,
    OCRServiceError,
    ocr_service,
)
from .schemas import (
    AnalyticsResponse,
    ClearHistoryResponse,
    DeleteResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    HistoryItem,
    HistoryListResponse,
    Limits,
    OCRResponse,
    OCRStatus,
    Patterns,
)
from .text_utils import count_lines, extract_patterns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger("glint.api")

CHUNK_SIZE = 256 * 1024  # 256 KB
UPLOAD_FILENAME = "upload.bin"  # never derived from the client supplied name
SNIFF_BYTES = 16  # enough bytes to recognize PDF / PNG / JPEG / WEBP


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
def get_ocr(request: Request) -> OCRService:
    """The OCR engine used by this request (swappable in tests)."""
    engine = getattr(request.app.state, "ocr", None)
    return engine if engine is not None else ocr_service


# ---------------------------------------------------------------------------
# Application life cycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s %s - data directory: %s",
        settings.app_name,
        settings.version,
        settings.data_dir.name,
    )
    app.state.db_ready = False
    try:
        await asyncio.to_thread(database.init_db)
        app.state.db_ready = True
    except Exception:
        logger.exception("Database initialization failed")

    # Tests may install a stub engine before start-up; respect it if present.
    engine = getattr(app.state, "ocr", None)
    if engine is None:
        engine = ocr_service
        app.state.ocr = engine

    # Model loading is CPU work: keep it off the event loop.
    await asyncio.to_thread(engine.initialize)
    if engine.is_ready:
        logger.info("Local OCR ready: %s", engine.engine_label)
    else:
        logger.error(
            "Local OCR is NOT ready. Uploads will be rejected with 503 until "
            "the engine can be initialized."
        )
    try:
        yield
    finally:
        logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title="GLINT API",
    description="Lightweight local OCR and document digitization.",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# CORS is limited to the real Vite development origins (no wildcard).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)


# ---------------------------------------------------------------------------
# Error handling - one JSON shape for everything
# ---------------------------------------------------------------------------
def error_response(
    status_code: int, code: str, message: str, details: Optional[dict] = None
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details or {})
    ).model_dump()
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(DocumentError)
async def handle_document_error(request: Request, exc: DocumentError):
    logger.warning("Rejected upload (%s): %s", exc.code, exc.message)
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(OCRServiceError)
async def handle_ocr_error(request: Request, exc: OCRServiceError):
    logger.error("OCR failure (%s): %s", exc.code, exc.message)
    return error_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    code = "not_found" if exc.status_code == 404 else "http_error"
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    if exc.status_code == 404:
        message = message or "The requested resource was not found."
    return error_response(exc.status_code, code, str(message))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    # Only field names are echoed back - never internal values or paths.
    fields = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        fields.append({"field": location, "message": error.get("msg", "")})
    return error_response(
        422,
        "invalid_request",
        "The request could not be understood. Please attach a single document "
        "file and try again.",
        {"fields": fields},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled error while serving %s", request.url.path)
    return error_response(
        500,
        "internal_error",
        "Something went wrong inside Glint. The details were written to the "
        "backend log.",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health(request: Request, engine: OCRService = Depends(get_ocr)):
    """Liveness plus an honest OCR readiness report."""
    return HealthResponse(
        status="ok" if getattr(request.app.state, "db_ready", False) else "degraded",
        app=settings.app_name,
        version=settings.version,
        tagline=settings.tagline,
        ocr=OCRStatus(**engine.status()),
        limits=Limits(**settings.public_limits()),
        database_ready=bool(getattr(request.app.state, "db_ready", False)),
    )


@app.post("/api/ocr", response_model=OCRResponse, tags=["ocr"])
def run_ocr(
    request: Request,
    engine: OCRService = Depends(get_ocr),
    file: UploadFile = File(...),
):
    """Validate one upload, run local OCR page by page and store the result."""
    # 1. Fail fast when the local engine is unusable.
    if not engine.is_ready:
        engine.initialize()
    if not engine.is_ready:
        status = engine.status()
        raise OCRNotReadyError(
            status.get("error") or "The local OCR engine is not available."
        )

    # 2. Reject obviously oversized uploads before reading the whole body.
    #    A small tolerance covers the multipart framing overhead.
    declared = request.headers.get("content-length")
    if declared:
        try:
            declared_size = int(declared)
        except ValueError:
            declared_size = 0
        if declared_size > settings.max_file_size_bytes + MEGABYTE:
            raise FileTooLargeError(
                f"This file is larger than the {settings.max_file_size_mb} MB limit.",
                details={"max_bytes": settings.max_file_size_bytes},
            )

    if not file or not file.filename:
        raise UnsupportedFormatError(
            "No file was attached. Choose a PDF, PNG, JPG or WEBP document."
        )

    return _process_upload(engine, file)


def _process_upload(engine: OCRService, file: UploadFile) -> OCRResponse:
    """Save the upload to a temporary directory, run OCR, store the result.

    The temporary directory is removed in the ``finally`` block, so no trace of
    the original document survives the request - not even after an exception.
    """
    started = time.perf_counter()
    workdir = Path(tempfile.mkdtemp(prefix="glint-upload-"))
    target = workdir / UPLOAD_FILENAME
    written = 0
    head = b""  # first bytes, kept in memory for content sniffing

    try:
        with target.open("wb") as output:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_file_size_bytes:
                    raise FileTooLargeError(
                        f"This file is larger than the "
                        f"{settings.max_file_size_mb} MB limit.",
                        details={
                            "max_bytes": settings.max_file_size_bytes,
                            "received_bytes": written,
                        },
                    )
                if len(head) < SNIFF_BYTES:
                    head += chunk[: SNIFF_BYTES - len(head)]
                output.write(chunk)

        if written == 0:
            raise EmptyFileError("The uploaded file is empty.")

        # The real content type is decided from the bytes, never from the
        # filename or from the MIME type the browser claims.
        kind = sniff_document_kind(head, file.filename or "")

        result = process_document(
            target,
            filename=file.filename or "document",
            size_bytes=written,
            kind=kind,
            engine=engine,
        )

        record = database.insert_job(
            filename=result.filename,
            file_type=result.file_type,
            pages=result.pages,
            engine=result.engine,
            duration_ms=result.duration_ms,
            char_count=result.char_count,
            text=result.text,
        )

        logger.info(
            "OCR finished in %.0f ms (%s, %s page(s), %s characters)",
            (time.perf_counter() - started) * 1000.0,
            result.file_type,
            result.pages,
            result.char_count,
        )
        return OCRResponse(
            job_id=record["id"],
            filename=result.filename,
            file_type=result.file_type,
            pages=result.pages,
            engine=result.engine,
            duration_ms=result.duration_ms,
            char_count=result.char_count,
            line_count=result.line_count or count_lines(result.text),
            text=result.text,
            patterns=Patterns(**extract_patterns(result.text)),
            warnings=result.warnings,
            created_at=record["created_at"],
        )
    finally:
        # Starlette closes the spooled upload itself; we only remove our own
        # temporary directory (this also runs when an exception was raised).
        shutil.rmtree(workdir, ignore_errors=True)


@app.get("/api/history", response_model=HistoryListResponse, tags=["history"])
def list_history(search: Optional[str] = None, limit: Optional[int] = None):
    """Recent OCR jobs, newest first, optionally filtered by filename."""
    rows = database.list_jobs(search=search, limit=limit)
    return HistoryListResponse(
        items=[HistoryItem(**row) for row in rows],
        count=len(rows),
        search=search,
    )


@app.get("/api/history/{job_id}", response_model=OCRResponse, tags=["history"])
def get_history_item(job_id: str):
    """One stored job including its extracted text and detected patterns."""
    row = database.get_job(job_id)
    if row is None:
        return _missing_job(job_id)
    text = row.get("text") or ""
    return OCRResponse(
        job_id=row["id"],
        filename=row["filename"],
        file_type=row["file_type"],
        pages=row["pages"],
        engine=row["engine"],
        duration_ms=row["duration_ms"],
        char_count=row["char_count"],
        line_count=count_lines(text),
        text=text,
        patterns=Patterns(**extract_patterns(text)),
        warnings=(
            ["No text was recognized for this document."] if not text.strip() else []
        ),
        created_at=row["created_at"],
    )


def _missing_job(job_id: str) -> None:
    """Raise the standard 404 used for unknown history entries."""
    logger.warning("History entry not found: %s", job_id)
    raise HTTPException(status_code=404, detail="This history entry does not exist.")


@app.delete("/api/history/{job_id}", response_model=DeleteResponse, tags=["history"])
def delete_history_item(job_id: str):
    """Delete a single history entry."""
    removed = database.delete_job(job_id)
    if not removed:
        return _missing_job(job_id)
    return DeleteResponse(deleted=True, job_id=job_id)


@app.delete("/api/history", response_model=ClearHistoryResponse, tags=["history"])
def clear_history():
    """Delete the whole history (the frontend asks for confirmation first)."""
    removed = database.clear_jobs()
    logger.info("History cleared (%s record(s) removed)", removed)
    return ClearHistoryResponse(deleted=True, deleted_count=removed)


@app.get("/api/analytics", response_model=AnalyticsResponse, tags=["analytics"])
def analytics():
    """Real metrics computed from the stored history with pandas."""
    rows = database.fetch_all_jobs()
    summary: Dict[str, Any] = compute_summary(rows)
    summary["chart_available"] = True
    return AnalyticsResponse(**summary)


@app.get("/api/analytics/chart", tags=["analytics"])
def analytics_chart():
    """The matplotlib chart as a PNG. Empty history returns an empty-state PNG."""
    rows = database.fetch_all_jobs()
    png = render_chart_png(rows)
    if png is None:  # pragma: no cover - render_chart_png always returns bytes
        return error_response(
            503, "chart_unavailable", "The chart could not be rendered."
        )
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/api/config", tags=["system"])
def public_config(engine: OCRService = Depends(get_ocr)):
    """Non-secret configuration the UI needs (limits, brand, OCR label)."""
    return {
        "app": settings.app_name,
        "tagline": settings.tagline,
        "version": settings.version,
        "limits": settings.public_limits(),
        "ocr": engine.status(),
        "frontend_origin": settings.frontend_origin,
    }


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
def api_not_found(path: str):
    """Unknown API endpoints answer with the shared JSON error shape.

    Registered after the real routes but before the optional static mount, so
    a missing /api/... path never returns an HTML 404 page.
    """
    logger.warning("Unknown API endpoint: /api/%s", path)
    raise HTTPException(status_code=404, detail="Unknown API endpoint.")


# ---------------------------------------------------------------------------
# Optional: serve the production frontend build from the same process
# ---------------------------------------------------------------------------
def mount_frontend_build(application: FastAPI) -> bool:
    """Serve ``frontend/dist`` when it exists (handy for a single-process run)."""
    dist = PROJECT_ROOT / "frontend" / "dist"
    if not settings.serve_frontend or not dist.is_dir():
        return False
    application.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    logger.info("Serving the built frontend from frontend/dist")
    return True


mount_frontend_build(app)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        workers=1,
        reload=False,
    )
