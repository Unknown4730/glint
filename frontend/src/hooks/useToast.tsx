import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import type { ToastMessage } from '../types'

interface ToastContextValue {
  push: (toast: Omit<ToastMessage, 'id'>) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const LIFETIME_MS = 4800

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const nextId = useRef(1)
  const timers = useRef<number[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const push = useCallback(
    (toast: Omit<ToastMessage, 'id'>) => {
      const id = nextId.current++
      setToasts((current) => [...current.slice(-3), { ...toast, id }])
      const timer = window.setTimeout(() => dismiss(id), LIFETIME_MS)
      timers.current.push(timer)
    },
    [dismiss],
  )

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((timer) => window.clearTimeout(timer))
  }, [])

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[min(23rem,calc(100vw-2.5rem))] flex-col gap-2.5"
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <ToastCard key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastMessage
  onDismiss: (id: number) => void
}) {
  const Icon =
    toast.tone === 'success' ? CheckCircle2 : toast.tone === 'error' ? AlertTriangle : Info
  const accent =
    toast.tone === 'success'
      ? 'text-success'
      : toast.tone === 'error'
        ? 'text-danger'
        : 'text-lime'

  return (
    <div className="pointer-events-auto animate-fade-up rounded-xl border border-line bg-raised/95 p-3.5 shadow-panel backdrop-blur-sm">
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-[18px] w-[18px] shrink-0 ${accent}`} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-medium leading-snug text-ink">{toast.title}</p>
          {toast.description ? (
            <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{toast.description}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => onDismiss(toast.id)}
          className="-m-1 rounded-md p-1 text-faint transition hover:bg-white/5 hover:text-ink"
          aria-label="Dismiss notification"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used inside a <ToastProvider>')
  }
  return context
}
