import { useEffect } from 'react'
import { Copy, Download, X } from 'lucide-react'
import type { OCRResult } from '../types'
import { Button } from './Button'
import { formatDateTime, formatNumber } from '../lib/format'

export interface ReadingOverlayProps {
  result: OCRResult
  copied: boolean
  onCopy: () => void
  onDownload: () => void
  onClose: () => void
}

/**
 * A calm full-screen reading view for long documents.
 * Escape closes it; the text stays selectable.
 */
export function ReadingOverlay({
  result,
  copied,
  onCopy,
  onDownload,
  onClose,
}: ReadingOverlayProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [onClose])

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-canvas/95 backdrop-blur-sm">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3 sm:px-6">
        <div className="min-w-0">
          <p className="truncate text-[14px] font-semibold text-ink">{result.filename}</p>
          <p className="mt-0.5 truncate text-[11.5px] text-muted">
            {result.pages} page{result.pages === 1 ? '' : 's'} ·{' '}
            {formatNumber(result.char_count)} characters · {formatDateTime(result.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button size="sm" onClick={onCopy} icon={<Copy />}>
            {copied ? 'Copied' : 'Copy'}
          </Button>
          <Button size="sm" onClick={onDownload} icon={<Download />}>
            .txt
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onClose}
            icon={<X />}
            aria-label="Close reading view"
          >
            Close
          </Button>
        </div>
      </div>

      <div className="scroll-slim flex-1 overflow-y-auto px-4 py-6 sm:px-8">
        <pre className="mx-auto max-w-3xl whitespace-pre-wrap break-words font-sans text-[14.5px] leading-[1.75] text-ink/95">
          {result.text || 'No text was recognized.'}
        </pre>
      </div>
    </div>
  )
}
