"""Pydantic models describing the JSON that Glint sends to the frontend.

Keeping them in one place means the React types in
``frontend/src/types/index.ts`` have a single source of truth to mirror.

Concepts demonstrated: typed data validation and serialization with pydantic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OCRStatus(BaseModel):
    ready: bool
    engine: str = "rapidocr"
    engine_version: Optional[str] = None
    runtime: str = "onnxruntime"
    runtime_version: Optional[str] = None
    model: str
    device: str = "cpu"
    error_code: Optional[str] = None
    error: Optional[str] = None


class Limits(BaseModel):
    max_file_size_mb: int
    max_pdf_pages: int
    max_image_side_px: int
    pdf_render_dpi: int
    accepted_extensions: List[str]


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "GLINT"
    version: str
    tagline: str
    ocr: OCRStatus
    limits: Limits
    database_ready: bool = True


class Patterns(BaseModel):
    emails: List[str] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)
    currency: List[str] = Field(default_factory=list)


class OCRResponse(BaseModel):
    """The answer to ``POST /api/ocr`` and to ``GET /api/history/{job_id}``."""

    job_id: str
    filename: str
    file_type: str
    pages: int
    engine: str
    duration_ms: float
    char_count: int
    line_count: int = 0
    text: str
    patterns: Patterns
    warnings: List[str] = Field(default_factory=list)
    created_at: str


class HistoryItem(BaseModel):
    id: str
    filename: str
    file_type: str
    pages: int
    engine: str
    duration_ms: float
    char_count: int
    created_at: str


class HistoryListResponse(BaseModel):
    items: List[HistoryItem]
    count: int
    search: Optional[str] = None


class DeleteResponse(BaseModel):
    deleted: bool = True
    job_id: Optional[str] = None


class ClearHistoryResponse(BaseModel):
    deleted: bool = True
    deleted_count: int


class AnalyticsResponse(BaseModel):
    has_data: bool
    total_documents: int
    total_pages: int
    total_characters: int
    average_duration_ms: float
    fastest_duration_ms: float = 0.0
    slowest_duration_ms: float = 0.0
    most_common_file_type: Optional[str] = None
    file_type_counts: Dict[str, int] = Field(default_factory=dict)
    last_processed_at: Optional[str] = None
    chart_available: bool = True


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """The one JSON error shape used by every failure in Glint."""

    error: ErrorDetail
