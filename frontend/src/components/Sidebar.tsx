import { BarChart3, Cpu, History, Info, ScanText } from 'lucide-react'
import type { Health, ViewKey } from '../types'

export interface NavItem {
  key: ViewKey
  label: string
  icon: typeof ScanText
  description: string
}

export const NAV_ITEMS: NavItem[] = [
  { key: 'workspace', label: 'Workspace', icon: ScanText, description: 'Upload and extract' },
  { key: 'history', label: 'History', icon: History, description: 'Saved results' },
  { key: 'analytics', label: 'Analytics', icon: BarChart3, description: 'Usage summary' },
  { key: 'about', label: 'About Glint', icon: Info, description: 'How it works' },
]

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="relative flex h-9 w-9 items-center justify-center rounded-[11px] border border-line bg-raised">
        <svg viewBox="0 0 64 64" className="h-[22px] w-[22px]" aria-hidden="true">
          <path
            d="M32 8 L37 25.5 L54.5 30.5 L37 35.5 L32 53 L27 35.5 L9.5 30.5 L27 25.5 Z"
            fill="#C7F36B"
          />
        </svg>
      </span>
      <span className="min-w-0">
        <span className="block text-[15px] font-semibold uppercase tracking-[0.22em] text-ink">
          Glint
        </span>
        {!compact ? (
          <span className="block truncate text-[10.5px] uppercase tracking-[0.16em] text-faint">
            See beyond the page
          </span>
        ) : null}
      </span>
    </div>
  )
}

function StatusDot({ state }: { state: 'ok' | 'busy' | 'warn' | 'down' }) {
  const colors: Record<string, string> = {
    ok: 'bg-success',
    busy: 'bg-lime animate-breathe',
    warn: 'bg-warning',
    down: 'bg-danger',
  }
  return <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${colors[state]}`} aria-hidden="true" />
}

function EngineStatus({
  health,
  loading,
  offline,
}: {
  health: Health | null
  loading: boolean
  offline: boolean
}) {
  let state: 'ok' | 'busy' | 'warn' | 'down' = 'busy'
  let label = 'Connecting…'
  let detail = 'Talking to the local backend'

  if (offline) {
    state = 'down'
    label = 'Backend offline'
    detail = 'Start it with start.ps1'
  } else if (loading) {
    state = 'busy'
    label = 'Checking engine…'
    detail = 'Reading /api/health'
  } else if (health && health.ocr.ready) {
    state = 'ok'
    label = 'OCR ready'
    detail = health.ocr.model
  } else if (health) {
    state = 'warn'
    label = 'OCR unavailable'
    detail = health.ocr.error ?? 'Engine could not start'
  }

  return (
    <div className="rounded-xl border border-line bg-raised/70 p-3">
      <div className="flex items-center gap-2">
        <StatusDot state={state} />
        <p className="text-[12.5px] font-medium text-ink">{label}</p>
      </div>
      <p className="mt-1 line-clamp-2 pl-3.5 text-[11.5px] leading-snug text-muted">{detail}</p>
      <div className="mt-2.5 flex items-center gap-1.5 border-t border-line-soft pt-2.5 pl-0.5 text-[11px] text-faint">
        <Cpu className="h-3.5 w-3.5" aria-hidden="true" />
        <span>CPU only · nothing leaves this PC</span>
      </div>
    </div>
  )
}

export interface SidebarProps {
  view: ViewKey
  onNavigate: (view: ViewKey) => void
  health: Health | null
  healthLoading: boolean
  backendOffline: boolean
}

export function Sidebar({ view, onNavigate, health, healthLoading, backendOffline }: SidebarProps) {
  return (
    <aside className="sticky top-0 hidden h-screen w-[252px] shrink-0 flex-col border-r border-line bg-surface/70 px-4 py-5 lg:flex">
      <div className="px-1.5">
        <Brand />
      </div>

      <nav className="mt-7 flex flex-1 flex-col gap-1" aria-label="Main">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const active = item.key === view
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onNavigate(item.key)}
              aria-current={active ? 'page' : undefined}
              className={[
                'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors duration-150',
                active
                  ? 'bg-raised text-ink'
                  : 'text-muted hover:bg-raised/55 hover:text-ink',
              ].join(' ')}
            >
              <span
                className={[
                  'absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full transition-all duration-200',
                  active ? 'bg-lime opacity-100' : 'bg-lime opacity-0',
                ].join(' ')}
                aria-hidden="true"
              />
              <Icon
                className={`h-[18px] w-[18px] shrink-0 ${active ? 'text-lime' : 'text-faint group-hover:text-muted'}`}
                aria-hidden="true"
              />
              <span className="min-w-0">
                <span className="block truncate text-[13.5px] font-medium">{item.label}</span>
                <span className="block truncate text-[11px] text-faint">{item.description}</span>
              </span>
            </button>
          )
        })}
      </nav>

      <div className="mt-4">
        <EngineStatus health={health} loading={healthLoading} offline={backendOffline} />
      </div>

      <p className="mt-3 px-1 text-[10.5px] leading-relaxed text-faint">
        Glint v{health?.version ?? '1.0.0'} · local OCR
      </p>
    </aside>
  )
}

/** Compact navigation for narrow screens (the sidebar is hidden below lg). */
export function MobileNav({
  view,
  onNavigate,
  health,
  backendOffline,
}: {
  view: ViewKey
  onNavigate: (view: ViewKey) => void
  health: Health | null
  backendOffline: boolean
}) {
  const ready = Boolean(health?.ocr.ready) && !backendOffline
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur lg:hidden">
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <Brand compact />
        <span className="flex items-center gap-1.5 text-[11.5px] text-muted">
          <StatusDot state={backendOffline ? 'down' : ready ? 'ok' : 'warn'} />
          {backendOffline ? 'Backend offline' : ready ? 'OCR ready' : 'OCR unavailable'}
        </span>
      </div>
      <nav className="scroll-slim flex gap-1 overflow-x-auto px-3 pb-2.5" aria-label="Main">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const active = item.key === view
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onNavigate(item.key)}
              aria-current={active ? 'page' : undefined}
              className={[
                'flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition-colors',
                active ? 'bg-raised text-ink' : 'text-muted hover:bg-raised/60 hover:text-ink',
              ].join(' ')}
            >
              <Icon className={`h-4 w-4 ${active ? 'text-lime' : 'text-faint'}`} aria-hidden="true" />
              {item.label}
            </button>
          )
        })}
      </nav>
    </header>
  )
}
