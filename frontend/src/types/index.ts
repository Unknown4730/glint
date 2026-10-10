/**
 * Types shared by every Glint screen.
 * They mirror the pydantic models in `backend/app/schemas.py`.
 */

export type ViewKey = 'workspace' | 'history' | 'analytics' | 'about'

export type FileKind = 'pdf' | 'png' | 'jpeg' | 'webp' | string

export interface OCRStatus {
  ready: boolean
  engine: string
  engine_version: string | null
  runtime: string
  runtime_version: string | null
  model: string
  device: string
  error_code: string | null
  error: string | null
}

export interface Limits {
  max_file_size_mb: number
  max_pdf_pages: number
  max_image_side_px: number
  pdf_render_dpi: number
  accepted_extensions: string[]
}

export interface Health {
  status: string
  app: string
  version: string
  tagline: string
  ocr: OCRStatus
  limits: Limits
  database_ready: boolean
}

export interface Patterns {
  emails: string[]
  dates: string[]
  currency: string[]
}

/** Response of POST /api/ocr and GET /api/history/{id}. */
export interface OCRResult {
  job_id: string
  filename: string
  file_type: FileKind
  pages: number
  engine: string
  duration_ms: number
  char_count: number
  line_count: number
  text: string
  patterns: Patterns
  warnings: string[]
  created_at: string
}

/** One row of GET /api/history (no text, on purpose). */
export interface HistoryItem {
  id: string
  filename: string
  file_type: FileKind
  pages: number
  engine: string
  duration_ms: number
  char_count: number
  created_at: string
}

export interface HistoryList {
  items: HistoryItem[]
  count: number
  search: string | null
}

export interface Analytics {
  has_data: boolean
  total_documents: number
  total_pages: number
  total_characters: number
  average_duration_ms: number
  fastest_duration_ms: number
  slowest_duration_ms: number
  most_common_file_type: string | null
  file_type_counts: Record<string, number>
  last_processed_at: string | null
  chart_available: boolean
}

export interface DeleteResponse {
  deleted: boolean
  job_id: string | null
}

export interface ClearHistoryResponse {
  deleted: boolean
  deleted_count: number
}

/** The single JSON error shape produced by the backend. */
export interface ApiErrorPayload {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}

export interface ToastMessage {
  id: number
  tone: 'success' | 'error' | 'info'
  title: string
  description?: string
}
