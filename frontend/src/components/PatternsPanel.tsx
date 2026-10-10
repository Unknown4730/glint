import { Banknote, CalendarDays, Mail, SearchX } from 'lucide-react'
import type { Patterns } from '../types'

const GROUPS = [
  { key: 'emails', label: 'Email addresses', icon: Mail },
  { key: 'dates', label: 'Date-like strings', icon: CalendarDays },
  { key: 'currency', label: 'Currency amounts', icon: Banknote },
] as const

export function PatternsPanel({ patterns }: { patterns: Patterns }) {
  const total = GROUPS.reduce((sum, group) => sum + patterns[group.key].length, 0)

  return (
    <div className="rounded-xl border border-line bg-raised/50 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[13px] font-semibold text-ink">Detected patterns</h3>
        <span className="text-[11.5px] text-faint">
          {total === 0 ? 'none found' : `${total} match${total === 1 ? '' : 'es'}`}
        </span>
      </div>
      <p className="mt-1 text-[11.5px] leading-relaxed text-faint">
        Plain regular expressions over the recognized text — not AI extraction. Treat every match
        as a hint, not as a verified fact.
      </p>

      {total === 0 ? (
        <div className="mt-3.5 flex items-center gap-2.5 rounded-lg border border-line-soft bg-surface/60 px-3 py-2.5 text-[12.5px] text-muted">
          <SearchX className="h-4 w-4 shrink-0 text-faint" aria-hidden="true" />
          No email addresses, dates or amounts were found in this document.
        </div>
      ) : (
        <div className="mt-3.5 space-y-3">
          {GROUPS.map((group) => {
            const values = patterns[group.key]
            if (values.length === 0) return null
            const Icon = group.icon
            return (
              <div key={group.key}>
                <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.07em] text-faint">
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {group.label}
                  <span className="text-lime/80">· {values.length}</span>
                </div>
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {values.map((value) => (
                    <li
                      key={`${group.key}-${value}`}
                      className="max-w-full truncate rounded-md border border-line bg-surface px-2 py-1 font-mono text-[11.5px] text-ink"
                      title={value}
                    >
                      {value}
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
