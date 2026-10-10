import type { ReactNode } from 'react'
import { AlertTriangle, Info, OctagonAlert, X } from 'lucide-react'

type Tone = 'error' | 'warning' | 'info' | 'success'

const STYLES: Record<Tone, { box: string; icon: string; Icon: typeof Info }> = {
  error: {
    box: 'border-danger/35 bg-danger/[0.08]',
    icon: 'text-danger',
    Icon: OctagonAlert,
  },
  warning: {
    box: 'border-warning/30 bg-warning/[0.07]',
    icon: 'text-warning',
    Icon: AlertTriangle,
  },
  info: {
    box: 'border-line bg-raised',
    icon: 'text-lime',
    Icon: Info,
  },
  success: {
    box: 'border-success/30 bg-success/[0.07]',
    icon: 'text-success',
    Icon: Info,
  },
}

export interface AlertProps {
  tone?: Tone
  title: ReactNode
  children?: ReactNode
  onDismiss?: () => void
  className?: string
}

export function Alert({ tone = 'info', title, children, onDismiss, className = '' }: AlertProps) {
  const style = STYLES[tone]
  const Icon = style.Icon
  const role = tone === 'error' ? 'alert' : 'status'

  return (
    <div
      role={role}
      className={`flex animate-fade-in items-start gap-3 rounded-xl border px-4 py-3 ${style.box} ${className}`}
    >
      <Icon className={`mt-0.5 h-[18px] w-[18px] shrink-0 ${style.icon}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-[13.5px] font-medium leading-snug text-ink">{title}</p>
        {children ? (
          <div className="mt-1 text-[12.5px] leading-relaxed text-muted">{children}</div>
        ) : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="-m-1 rounded-md p-1 text-faint transition hover:bg-white/5 hover:text-ink"
          aria-label="Dismiss message"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  )
}
