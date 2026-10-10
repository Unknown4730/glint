import { useMemo, useState } from 'react'
import {
  Check,
  Clock3,
  Copy,
  Download,
  FileText,
  Hash,
  History,
  Maximize2,
  RotateCcw,
  ScanLine,
} from 'lucide-react'
import type { OCRResult } from '../types'
import { useClipboard } from '../hooks/useClipboard'
import { useToast } from '../hooks/useToast'
import { formatDateTime, formatDuration, formatNumber, textFileNameFor } from '../lib/format'
import { Alert } from './Alert'
import { Button } from './Button'
import { FileTypeBadge } from './Badge'
import { PatternsPanel } from './PatternsPanel'
import { ReadingOverlay } from './ReadingOverlay'
import { StatCard } from './StatCard'

export interface ResultPanelProps {
  result: OCRResult
  onReset: () => void
  onOpenHistory?: () => void
}

export function ResultPanel({ result, onReset, onOpenHistory }: ResultPanelProps) {
  const { copied, copy } = useClipboard()
  const { push } = useToast()
  const [reading, setReading] = useState(false)

  const hasText = result.text.trim().length > 0
  const wordCount = useMemo(
    () => (hasText ? result.text.trim().split(/\s+/).length : 0),
    [hasText, result.text],
  )

  const handleCopy = async () => {
    if (!hasText) {
      push({ tone: 'info', title: 'There is no text to copy yet.' })
      return
    }
    const ok = await copy(result.text)
    push(
      ok
        ? {
            tone: 'success',
            title: 'Copied to clipboard',
            description: `${formatNumber(result.char_count)} characters from ${result.filename}.`,
          }
        : {
            tone: 'error',
            title: 'Copying failed',
            description: 'Your browser blocked clipboard access. Select the text manually instead.',
          },
    )
  }

  const handleDownload = () => {
    if (!hasText) {
      push({ tone: 'info', title: 'There is no text to download yet.' })
      return
    }
    try {
      const blob = new Blob([result.text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = textFileNameFor(result.filename)
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      // Give the browser a moment before the object URL is released.
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      push({ tone: 'success', title: 'Text file downloaded', description: anchor.download })
    } catch {
      push({
        tone: 'error',
        title: 'Download failed',
        description: 'The browser refused to save the file. Try the copy button instead.',
      })
    }
  }

  return (
    <div className="animate-fade-up space-y-4">
      <div className="rounded-card border border-line bg-surface shadow-panel">
        {/* header ------------------------------------------------------- */}
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line-soft px-5 py-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <FileTypeBadge fileType={result.file_type} />
              <h2 className="truncate text-[15px] font-semibold text-ink" title={result.filename}>
                {result.filename}
              </h2>
            </div>
            <p className="mt-1 text-[12px] text-muted">
              Extracted {formatDateTime(result.created_at)} · job {result.job_id}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant={copied ? 'primary' : 'secondary'}
              onClick={handleCopy}
              icon={copied ? <Check /> : <Copy />}
              disabled={!hasText}
            >
              {copied ? 'Copied' : 'Copy all'}
            </Button>
            <Button size="sm" onClick={handleDownload} icon={<Download />} disabled={!hasText}>
              Download .txt
            </Button>
          </div>
        </header>

        {/* metadata ----------------------------------------------------- */}
        <div className="grid grid-cols-2 gap-2.5 px-5 py-4 lg:grid-cols-4">
          <StatCard
            label="Pages"
            value={result.pages}
            hint={result.pages === 1 ? 'single page' : 'processed sequentially'}
            icon={<FileText />}
          />
          <StatCard
            label="Duration"
            value={formatDuration(result.duration_ms)}
            hint={
              result.pages > 1
                ? `${formatDuration(result.duration_ms / result.pages)} per page`
                : 'including rendering'
            }
            icon={<Clock3 />}
          />
          <StatCard
            label="Characters"
            value={formatNumber(result.char_count)}
            hint={`${formatNumber(result.line_count)} lines · ${formatNumber(wordCount)} words`}
            icon={<Hash />}
          />
          <StatCard
            label="OCR engine"
            value={<span className="text-[13.5px] font-medium">Local CPU</span>}
            hint={result.engine}
            icon={<ScanLine />}
          />
        </div>

        {/* warnings ----------------------------------------------------- */}
        {result.warnings.length > 0 ? (
          <div className="space-y-2 px-5 pb-4">
            {result.warnings.map((warning) => (
              <Alert key={warning} tone="warning" title={warning} />
            ))}
          </div>
        ) : null}

        {/* text --------------------------------------------------------- */}
        <div className="px-5 pb-5">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="text-[12.5px] font-medium uppercase tracking-[0.07em] text-faint">
              Extracted text
            </h3>
            {hasText ? (
              <Button size="sm" variant="ghost" onClick={() => setReading(true)} icon={<Maximize2 />}>
                Reading view
              </Button>
            ) : null}
          </div>

          {hasText ? (
            <div className="scroll-slim max-h-[46vh] overflow-y-auto rounded-xl border border-line bg-canvas/70 p-4">
              <pre className="whitespace-pre-wrap break-words font-sans text-[13.5px] leading-[1.75] text-ink/95">
                {result.text}
              </pre>
            </div>
          ) : (
            <div className="rounded-xl border border-line bg-canvas/50 px-4 py-8 text-center">
              <p className="text-[13.5px] font-medium text-ink">No text was recognized</p>
              <p className="mx-auto mt-1.5 max-w-md text-[12.5px] leading-relaxed text-muted">
                The document was processed successfully, but the OCR engine found no readable
                printed text. Blank pages, handwriting, very low contrast or unusual layouts are
                the usual reasons.
              </p>
            </div>
          )}
        </div>

        {/* patterns ----------------------------------------------------- */}
        <div className="border-t border-line-soft px-5 py-4">
          <PatternsPanel patterns={result.patterns} />
        </div>

        {/* footer actions ------------------------------------------------ */}
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line-soft px-5 py-3.5">
          <p className="text-[11.5px] text-faint">
            Saved to your local history. The original file was deleted after processing.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {onOpenHistory ? (
              <Button size="sm" variant="ghost" onClick={onOpenHistory} icon={<History />}>
                View history
              </Button>
            ) : null}
            <Button size="sm" onClick={onReset} icon={<RotateCcw />}>
              Process another document
            </Button>
          </div>
        </footer>
      </div>

      {reading ? (
        <ReadingOverlay
          result={result}
          copied={copied}
          onCopy={handleCopy}
          onDownload={handleDownload}
          onClose={() => setReading(false)}
        />
      ) : null}
    </div>
  )
}
