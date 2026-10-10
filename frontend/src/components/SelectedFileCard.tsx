import { FileText, Image as ImageIcon, X } from 'lucide-react'
import { formatBytes } from '../lib/format'

export interface SelectedFileCardProps {
  file: File
  onRemove: () => void
  disabled?: boolean
}

/** Shows what is about to be processed, with a way to reset. */
export function SelectedFileCard({ file, onRemove, disabled = false }: SelectedFileCardProps) {
  const isPdf = file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf'
  const Icon = isPdf ? FileText : ImageIcon

  return (
    <div className="flex animate-fade-up items-center gap-3 rounded-xl border border-line bg-raised px-3.5 py-3">
      <span
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border ${
          isPdf ? 'border-lime/30 bg-lime/10 text-lime' : 'border-line bg-surface text-muted'
        }`}
        aria-hidden="true"
      >
        <Icon className="h-[18px] w-[18px]" />
      </span>

      <div className="min-w-0 flex-1">
        <p className="truncate text-[13.5px] font-medium text-ink" title={file.name}>
          {file.name}
        </p>
        <p className="mt-0.5 text-[11.5px] text-muted tabular-nums">
          {formatBytes(file.size)} · {isPdf ? 'PDF document' : 'Image document'}
          {file.type ? ` · ${file.type}` : ''}
        </p>
      </div>

      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        className="shrink-0 rounded-lg border border-transparent p-1.5 text-faint transition hover:border-line hover:bg-surface hover:text-danger disabled:cursor-not-allowed disabled:opacity-40"
        aria-label={`Remove ${file.name}`}
        title="Remove file"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  )
}
