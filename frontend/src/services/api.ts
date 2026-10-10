/**
 * The one and only module that talks to the FastAPI backend.
 *
 * Every screen and hook imports from here, so there are no hardcoded URLs
 * scattered across the UI and the base URL can be changed in a single place
 * (the VITE_API_BASE_URL environment variable).
 *
 * By default the base URL is empty, which means requests are sent to the same
 * origin as the page ("/api/..."). The Vite dev server proxies that path to
 * http://127.0.0.1:8000, so the browser never needs CORS in development.
 */

import type {
  Analytics,
  ApiErrorPayload,
  ClearHistoryResponse,
  DeleteResponse,
  Health,
  HistoryItem,
  HistoryList,
  OCRResult,
} from '../types'

const rawBase = (import.meta.env.VITE_API_BASE_URL ?? '').trim()

/** Absolute or empty base URL, never ending with a slash. */
export const API_BASE = rawBase.replace(/\/+$/, '')

/** Where the browser actually sends requests (used in error messages). */
export const API_LABEL = API_BASE === '' ? 'the local backend' : API_BASE

const DEFAULT_TIMEOUT_MS = 20_000
/** CPU OCR of a 10 page PDF on an older laptop can legitimately take a while. */
const OCR_TIMEOUT_MS = 10 * 60_000

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: Record<string, unknown>

  constructor(message: string, code: string, status: number, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

function unreachableError(cause: unknown): ApiError {
  return new ApiError(
    `Glint cannot reach the backend. Start it with start.ps1 (it should listen on http://127.0.0.1:8000).`,
    'backend_unreachable',
    0,
    { reason: cause instanceof Error ? cause.message : String(cause) },
  )
}

function timeoutError(seconds: number): ApiError {
  return new ApiError(
    `The request did not finish within ${seconds} seconds. Large documents take longer on a CPU; try a smaller file or fewer pages.`,
    'timeout',
    0,
  )
}

/** Turn any failed response into an ApiError with a readable message. */
async function toApiError(response: Response): Promise<ApiError> {
  let message = ''
  let code = 'request_failed'
  let details: Record<string, unknown> = {}

  try {
    const body = (await response.json()) as ApiErrorPayload
    if (body && body.error) {
      message = body.error.message
      code = body.error.code
      details = body.error.details ?? {}
    }
  } catch {
    // Not JSON (for example a proxy error page) - fall through to the defaults.
  }

  if (!message) {
    const fallbacks: Record<number, string> = {
      400: 'The document was rejected. Check the format and try again.',
      404: 'That record does not exist any more.',
      413: 'The file is larger than the configured upload limit.',
      422: 'The request was malformed.',
      500: 'Glint hit an internal error. Check the backend console for details.',
      503: 'The local OCR engine is not available yet.',
    }
    message = fallbacks[response.status] ?? `Request failed (HTTP ${response.status}).`
  }

  return new ApiError(message, code, response.status, details)
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: BodyInit
  timeoutMs?: number
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { Accept: 'application/json', ...(init.headers ?? {}) },
    })

    if (!response.ok) {
      throw await toApiError(response)
    }
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw timeoutError(Math.round(timeoutMs / 1000))
    }
    throw unreachableError(error)
  } finally {
    clearTimeout(timer)
  }
}

function toFormData(file: File): FormData {
  const form = new FormData()
  // The field name must match the FastAPI parameter: `file`.
  form.append('file', file, file.name)
  return form
}

export const api = {
  /** GET /api/health - also used to learn the limits and OCR readiness. */
  health(): Promise<Health> {
    return request<Health>('/api/health')
  },

  /** POST /api/ocr - upload one document and run local OCR. */
  runOcr(file: File): Promise<OCRResult> {
    return request<OCRResult>('/api/ocr', {
      method: 'POST',
      body: toFormData(file),
      timeoutMs: OCR_TIMEOUT_MS,
    })
  },

  /** GET /api/history - recent jobs, optionally filtered by filename. */
  history(search?: string): Promise<HistoryList> {
    const query = search && search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''
    return request<HistoryList>(`/api/history${query}`)
  },

  /** GET /api/history/{id} - one stored result including its text. */
  historyItem(jobId: string): Promise<OCRResult> {
    return request<OCRResult>(`/api/history/${encodeURIComponent(jobId)}`)
  },

  /** DELETE /api/history/{id} */
  deleteHistoryItem(jobId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/api/history/${encodeURIComponent(jobId)}`, {
      method: 'DELETE',
    })
  },

  /** DELETE /api/history */
  clearHistory(): Promise<ClearHistoryResponse> {
    return request<ClearHistoryResponse>('/api/history', { method: 'DELETE' })
  },

  /** GET /api/analytics */
  analytics(): Promise<Analytics> {
    return request<Analytics>('/api/analytics')
  },

  /**
   * URL of the matplotlib chart. It is used as an <img src>, so the browser
   * fetches it directly. The cache key forces a reload after new jobs.
   */
  chartUrl(cacheKey: number | string = Date.now()): string {
    return `${API_BASE}/api/analytics/chart?v=${encodeURIComponent(String(cacheKey))}`
  },
}

export type { HistoryItem }
