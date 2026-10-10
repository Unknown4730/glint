import type { ReactNode } from 'react'

export interface StatCardProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  className?: string
}

/** Compact metric tile used for result metadata and analytics numbers. */
export function StatCard({ label, value, hint, icon, className = '' }: StatCardProps) {
  return (
    <div
      className={`rounded-xl border border-line bg-raised px-3.5 py-3 transition-colors duration-200 hover:border-[#3a404b] ${className}`}
    >
      <div className="flex items-center gap-1.5 text-faint">
        {icon ? <span className="[&>svg]:h-3.5 [&>svg]:w-3.5" aria-hidden="true">{icon}</span> : null}
        <span className="text-[11px] font-medium uppercase tracking-[0.08em]">{label}</span>
      </div>
      <div className="mt-1.5 truncate text-[19px] font-semibold leading-tight text-ink tabular-nums">
        {value}
      </div>
      {hint ? <div className="mt-1 truncate text-[11.5px] text-muted">{hint}</div> : null}
    </div>
  )
}
