/** Minimal loading indicator plus a "working" line used while OCR runs. */
export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      role="status"
      aria-label="Loading"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.22" strokeWidth="2.5" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function ProcessingIndicator({
  label = 'Extracting text locally…',
  detail,
}: {
  label?: string
  detail?: string
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-lime/25 bg-lime/[0.06] px-4 py-3">
      <span className="relative flex h-2.5 w-2.5 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-lime opacity-60" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-lime" />
      </span>
      <div className="min-w-0">
        <p className="text-[13.5px] font-medium text-ink">{label}</p>
        {detail ? <p className="mt-0.5 text-[12px] text-muted">{detail}</p> : null}
      </div>
    </div>
  )
}
