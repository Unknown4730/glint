import { useCallback, useRef, useState, type DragEvent } from 'react'
import { FileUp, UploadCloud } from 'lucide-react'
import type { Limits } from '../types'
import { formatBytes } from '../lib/format'

export interface DropzoneProps {
  limits: Limits | null
  disabled?: boolean
  hasFile?: boolean
  onFileSelected: (file: File) => void
  onRejected: (message: string) => void
}

/**
 * Drag-and-drop area plus a real file picker.
 *
 * The browser-side checks are only a courtesy: the backend re-validates size,
 * extension and - most importantly - the actual file content.
 */
export function Dropzone({
  limits,
  disabled = false,
  hasFile = false,
  onFileSelected,
  onRejected,
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const [dragging, setDragging] = useState(false)

  const accept = limits ? limits.accepted_extensions.join(',') : '.pdf,.png,.jpg,.jpeg,.webp'

  const handleFile = useCallback(
    (file: File | undefined | null) => {
      if (!file) return

      const extension = file.name.includes('.')
        ? `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
        : ''

      if (limits && !limits.accepted_extensions.includes(extension)) {
        onRejected(
          `${file.name || 'That file'} is not a supported format. Glint reads PDF, PNG, JPG and WEBP.`,
        )
        return
      }
      if (file.size === 0) {
        onRejected('That file is empty (0 bytes).')
        return
      }
      if (limits && file.size > limits.max_file_size_mb * 1024 * 1024) {
        onRejected(
          `${file.name} is ${formatBytes(file.size)}. The limit is ${limits.max_file_size_mb} MB.`,
        )
        return
      }
      onFileSelected(file)
    },
    [limits, onFileSelected, onRejected],
  )

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      dragDepth.current = 0
      setDragging(false)
      if (disabled) return

      const files = event.dataTransfer?.files
      if (!files || files.length === 0) {
        onRejected('Nothing was dropped. Try again with a document file.')
        return
      }
      if (files.length > 1) {
        onRejected('Glint processes one document at a time. The first file was ignored.')
      }
      handleFile(files[0])
    },
    [disabled, handleFile, onRejected],
  )

  const onDragEnter = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (disabled) return
      dragDepth.current += 1
      setDragging(true)
    },
    [disabled],
  )

  const onDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    dragDepth.current = Math.max(0, dragDepth.current - 1)
    if (dragDepth.current === 0) setDragging(false)
  }, [])

  return (
    <div
      onDragEnter={onDragEnter}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={[
        'relative overflow-hidden rounded-card border-2 border-dashed transition-all duration-200',
        'has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-lime/70 has-[:focus-visible]:ring-offset-2 has-[:focus-visible]:ring-offset-surface',
        dragging
          ? 'border-lime bg-lime/[0.07]'
          : 'border-line bg-raised/40 hover:border-[#3d434e] hover:bg-raised/70',
        disabled ? 'pointer-events-none opacity-50' : '',
      ].join(' ')}
    >
      {/* Scanning line, only while a file is being dragged over the area. */}
      {dragging ? (
        <span
          className="pointer-events-none absolute inset-x-6 top-0 h-px animate-scan bg-lime/70"
          aria-hidden="true"
        />
      ) : null}

      <label className="flex cursor-pointer flex-col items-center px-6 py-9 text-center">
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          disabled={disabled}
          onChange={(event) => {
            handleFile(event.target.files?.[0])
            // Allow picking the same file again after a reset.
            event.target.value = ''
          }}
        />

        <span
          className={`flex h-14 w-14 items-center justify-center rounded-2xl border transition-colors duration-200 ${
            dragging ? 'border-lime/50 bg-lime/15 text-lime' : 'border-line bg-surface text-lime'
          }`}
          aria-hidden="true"
        >
          {dragging ? <FileUp className="h-6 w-6" /> : <UploadCloud className="h-6 w-6" />}
        </span>

        <span className="mt-4 text-[15px] font-semibold text-ink">
          {dragging ? 'Drop it here' : hasFile ? 'Replace the document' : 'Drop a document here'}
        </span>
        <span className="mt-1 text-[12.5px] text-muted">
          or{' '}
          <span className="font-medium text-lime underline decoration-lime/40 decoration-dotted underline-offset-4">
            browse your files
          </span>{' '}
          — one document at a time
        </span>

        <span className="mt-5 flex flex-wrap items-center justify-center gap-1.5">
          {(limits?.accepted_extensions ?? ['.pdf', '.png', '.jpg', '.jpeg', '.webp']).map((ext) => (
            <span
              key={ext}
              className="rounded-md border border-line bg-surface px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted"
            >
              {ext.replace('.', '')}
            </span>
          ))}
        </span>

        <span className="mt-3 text-[11.5px] leading-relaxed text-faint">
          {limits
            ? `Up to ${limits.max_file_size_mb} MB · ${limits.max_pdf_pages} PDF pages · rendered at ${limits.pdf_render_dpi} DPI`
            : 'Reading limits from the backend…'}
        </span>
      </label>
    </div>
  )
}
