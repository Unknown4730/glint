import type { ReactNode } from 'react'

export interface PanelProps {
  title?: ReactNode
  subtitle?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}

/**
 * The standard surface used across Glint: a raised card with a hairline border,
 * an optional header row and consistent padding.
 */
export function Panel({
  title,
  subtitle,
  icon,
  actions,
  children,
  className = '',
  bodyClassName = '',
}: PanelProps) {
  return (
    <section
      className={`rounded-card border border-line bg-surface shadow-panel ${className}`}
    >
      {title ? (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            {icon ? (
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-line bg-raised text-lime [&>svg]:h-[17px] [&>svg]:w-[17px]">
                {icon}
              </span>
            ) : null}
            <div className="min-w-0">
              <h2 className="truncate text-[15px] font-semibold tracking-tight text-ink">
                {title}
              </h2>
              {subtitle ? (
                <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted">{subtitle}</p>
              ) : null}
            </div>
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className={`px-5 py-4 ${bodyClassName}`}>{children}</div>
    </section>
  )
}
