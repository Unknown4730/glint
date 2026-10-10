import type { ReactNode } from 'react'
import { fileTypeLabel } from '../lib/format'

type Tone = 'neutral' | 'lime' | 'danger' | 'success' | 'warning'

const TONES: Record<Tone, string> = {
  neutral: 'border-line bg-raised text-muted',
  lime: 'border-lime/35 bg-lime/10 text-lime',
  danger: 'border-danger/35 bg-danger/10 text-danger',
  success: 'border-success/30 bg-success/10 text-success',
  warning: 'border-warning/30 bg-warning/10 text-warning',
}

export function Badge({
  children,
  tone = 'neutral',
  className = '',
}: {
  children: ReactNode
  tone?: Tone
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium uppercase tracking-[0.06em] ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

/** Small badge showing the document type (PDF / PNG / JPG / WEBP). */
export function FileTypeBadge({ fileType }: { fileType: string }) {
  return <Badge tone={fileType === 'pdf' ? 'lime' : 'neutral'}>{fileTypeLabel(fileType)}</Badge>
}
