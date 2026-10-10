import type { ReactNode } from 'react'

export interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: ReactNode
  action?: ReactNode
  className?: string
}

/**
 * A calm, informative placeholder. Glint never shows an empty box without
 * explaining what the user can do next.
 */
export function EmptyState({ icon, title, description, action, className = '' }: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center px-6 py-12 text-center ${className}`}
    >
      <span className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-raised text-lime">
        <span className="absolute inset-0 rounded-2xl bg-lime/[0.07]" aria-hidden="true" />
        <span className="relative [&>svg]:h-6 [&>svg]:w-6" aria-hidden="true">
          {icon}
        </span>
      </span>
      <h3 className="mt-4 text-[15px] font-semibold text-ink">{title}</h3>
      <div className="mt-1.5 max-w-md text-[13px] leading-relaxed text-muted">{description}</div>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}
