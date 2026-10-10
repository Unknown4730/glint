import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Cpu,
  FileWarning,
  Loader2,
  RefreshCw,
  ScanText,
  ShieldCheck,
  Sparkles,
  Upload,
} from 'lucide-react'
import type { Health, OCRResult, ViewKey } from '../types'
import { ApiError, api } from '../services/api'
import { useToast } from '../hooks/useToast'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Dropzone } from '../components/Dropzone'
import { EmptyState } from '../components/EmptyState'
import { Panel } from '../components/Panel'
import { ProcessingIndicator } from '../components/Spinner'
import { ResultPanel } from '../components/ResultPanel'
import { SelectedFileCard } from '../components/SelectedFileCard'

export interface WorkspacePageProps {
  health: Health | null
  backendOffline: boolean
  onRefreshHealth: () => void
  result: OCRResult | null
  onResult: (result: OCRResult | null) => void
  onNavigate: (view: ViewKey) => void
}

const STEPS = [
  { title: 'Validate', detail: 'Size, real content type and page count are checked first.' },
  { title: 'Render', detail: 'PDF pages are rasterized one at a time at a conservative DPI.' },
  { title: 'Recognize', detail: 'The local ONNX engine reads the printed text on your CPU.' },
  { title: 'Save', detail: 'Text and metadata go to SQLite; the file itself is deleted.' },
]

export function WorkspacePage({
  health,
  backendOffline,
  onRefreshHealth,
  result,
  onResult,
  onNavigate,
}: WorkspacePageProps) {
  const { push } = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current)
    }
  }, [])

  const startTimer = useCallback(() => {
    setElapsed(0)
    if (timer.current !== null) window.clearInterval(timer.current)
    const startedAt = Date.now()
    timer.current = window.setInterval(() => {
      setElapsed(Math.round((Date.now() - startedAt) / 1000))
    }, 250)
  }, [])

  const stopTimer = useCallback(() => {
    if (timer.current !== null) window.clearInterval(timer.current)
    timer.current = null
  }, [])

  const handleExtract = useCallback(async () => {
    if (!file || processing) return
    setProcessing(true)
    setError(null)
    startTimer()
    try {
      const response = await api.runOcr(file)
      onResult(response)
      push({
        tone: response.char_count > 0 ? 'success' : 'info',
        title:
          response.char_count > 0
            ? `Extracted ${response.char_count.toLocaleString()} characters`
            : 'Processing finished with no text',
        description:
          response.char_count > 0
            ? `${response.pages} page${response.pages === 1 ? '' : 's'} · ${(
                response.duration_ms / 1000
              ).toFixed(2)} s · saved to history`
            : 'The engine found nothing readable on this document.',
      })
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Something unexpected went wrong while contacting the backend.'
      setError(message)
      push({ tone: 'error', title: 'Extraction failed', description: message })
    } finally {
      stopTimer()
      setProcessing(false)
    }
  }, [file, processing, push, onResult, startTimer, stopTimer])

  const handleReset = useCallback(() => {
    setFile(null)
    setError(null)
    onResult(null)
  }, [onResult])

  const ocrUnavailable = health !== null && !health.ocr.ready

  return (
    <div className="space-y-5">
      {/* page header ---------------------------------------------------- */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-ink">
            Workspace
          </h1>
          <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-muted">
            Turn a scanned document, photo or PDF page into editable text. Glint runs a compact
            OCR model <span className="text-ink">entirely on this computer</span> — no cloud API,
            no account, no key.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[11.5px] text-muted">
            <ShieldCheck className="h-3.5 w-3.5 text-lime" aria-hidden="true" />
            Local processing
          </span>
          <Button size="sm" variant="ghost" onClick={onRefreshHealth} icon={<RefreshCw />}>
            Recheck engine
          </Button>
        </div>
      </div>

      {/* banners --------------------------------------------------------- */}
      {backendOffline ? (
        <Alert tone="error" title="The Glint backend is not responding">
          Start it with <code className="font-mono text-ink">start.ps1</code> (or{' '}
          <code className="font-mono text-ink">uvicorn app.main:app</code> inside{' '}
          <code className="font-mono text-ink">backend/</code>). It should listen on
          http://127.0.0.1:8000. Nothing is broken in your document — the API is simply not
          running yet.
        </Alert>
      ) : ocrUnavailable ? (
        <Alert tone="warning" title="The local OCR engine is not ready">
          {health?.ocr.error ??
            'RapidOCR could not be initialized. Re-run install.ps1 to install the OCR package and its bundled models.'}
        </Alert>
      ) : null}

      {/* main grid ------------------------------------------------------- */}
      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel
            title="Document"
            subtitle="One file at a time — the pipeline is deliberately sequential."
            icon={<Upload />}
            actions={
              file && !processing ? (
                <Button size="sm" variant="ghost" onClick={handleReset}>
                  Reset
                </Button>
              ) : null
            }
          >
            <div className="space-y-3.5">
              <Dropzone
                limits={health?.limits ?? null}
                disabled={processing}
                hasFile={Boolean(file)}
                onFileSelected={(selected) => {
                  setFile(selected)
                  setError(null)
                  onResult(null)
                }}
                onRejected={(message) => {
                  setError(message)
                  push({ tone: 'error', title: 'File rejected', description: message })
                }}
              />

              {file ? (
                <SelectedFileCard file={file} onRemove={handleReset} disabled={processing} />
              ) : null}

              {processing ? (
                <ProcessingIndicator
                  label={`Extracting text locally… ${elapsed}s`}
                  detail="Pages are processed one by one on the CPU. Please do not close this tab."
                />
              ) : null}

              {error && !processing ? (
                <Alert tone="error" title="Could not process that document" onDismiss={() => setError(null)}>
                  {error}
                </Alert>
              ) : null}

              <Button
                variant="primary"
                size="lg"
                className="w-full"
                onClick={handleExtract}
                disabled={!file || processing || backendOffline || ocrUnavailable}
                loading={processing}
                icon={processing ? <Loader2 /> : <Sparkles />}
              >
                {processing ? 'Processing…' : 'Extract Text'}
              </Button>

              <p className="flex items-start gap-2 text-[11.5px] leading-relaxed text-faint">
                <Cpu className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>
                  {!file
                    ? 'Choose a PDF, PNG, JPG or WEBP file to enable extraction.'
                    : backendOffline || ocrUnavailable
                      ? 'Fix the engine status above, then extract.'
                      : `Ready to process “${file.name}”.`}
                </span>
              </p>
            </div>
          </Panel>

          <Panel title="How it works" icon={<FileWarning />} className="hidden xl:block">
            <ol className="space-y-3">
              {STEPS.map((step, index) => (
                <li key={step.title} className="flex gap-3">
                  <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-line bg-raised text-[10.5px] font-semibold text-lime tabular-nums">
                    {index + 1}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[13px] font-medium text-ink">{step.title}</span>
                    <span className="block text-[12px] leading-relaxed text-muted">
                      {step.detail}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </Panel>
        </div>

        {/* result column ------------------------------------------------- */}
        <div>
          {result ? (
            <ResultPanel
              result={result}
              onReset={handleReset}
              onOpenHistory={() => onNavigate('history')}
            />
          ) : (
            <Panel className="min-h-[420px]">
              <EmptyState
                icon={<ScanText />}
                title={processing ? 'Reading your document…' : 'No result yet'}
                description={
                  processing ? (
                    <span>
                      Glint is rendering and recognizing pages locally. This can take a few
                      seconds per page on an older CPU.
                    </span>
                  ) : (
                    <span>
                      Drop a document on the left and press{' '}
                      <span className="font-medium text-ink">Extract Text</span>. The recognized
                      text, page count, duration, character count and any detected emails, dates
                      or amounts will appear here — and stay available in History.
                    </span>
                  )
                }
                action={
                  onNavigate ? (
                    <Button variant="secondary" size="sm" onClick={() => onNavigate('history')}>
                      Open previous results
                    </Button>
                  ) : undefined
                }
              />
            </Panel>
          )}
        </div>
      </div>
    </div>
  )
}
