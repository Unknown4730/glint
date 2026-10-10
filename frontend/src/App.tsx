import { useCallback, useMemo, useState } from 'react'
import type { OCRResult, ViewKey } from './types'
import { useHealth } from './hooks/useHealth'
import { MobileNav, Sidebar } from './components/Sidebar'
import { AboutPage } from './pages/AboutPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { HistoryPage } from './pages/HistoryPage'
import { WorkspacePage } from './pages/WorkspacePage'

export default function App() {
  const { health, loading, error, refresh } = useHealth()
  const [view, setView] = useState<ViewKey>('workspace')
  const [result, setResult] = useState<OCRResult | null>(null)
  // Bumped whenever the stored history changes, so History/Analytics reload.
  const [dataVersion, setDataVersion] = useState(0)

  const backendOffline = error !== null && error.code === 'backend_unreachable'

  const handleResult = useCallback((next: OCRResult | null) => {
    setResult(next)
    if (next) setDataVersion((version) => version + 1)
  }, [])

  const openFromHistory = useCallback((next: OCRResult) => {
    setResult(next)
    setView('workspace')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const navigate = useCallback((next: ViewKey) => {
    setView(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const shellProps = useMemo(
    () => ({ health, healthLoading: loading, backendOffline }),
    [health, loading, backendOffline],
  )

  return (
    <div className="flex min-h-screen">
      <Sidebar
        view={view}
        onNavigate={navigate}
        health={shellProps.health}
        healthLoading={shellProps.healthLoading}
        backendOffline={shellProps.backendOffline}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <MobileNav
          view={view}
          onNavigate={navigate}
          health={health}
          backendOffline={backendOffline}
        />

        <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {view === 'workspace' ? (
            <WorkspacePage
              health={health}
              backendOffline={backendOffline}
              onRefreshHealth={() => void refresh()}
              result={result}
              onResult={handleResult}
              onNavigate={navigate}
            />
          ) : null}

          {view === 'history' ? (
            <HistoryPage onOpenResult={openFromHistory} refreshKey={dataVersion} />
          ) : null}

          {view === 'analytics' ? (
            <AnalyticsPage
              refreshKey={dataVersion}
              onNavigateWorkspace={() => navigate('workspace')}
            />
          ) : null}

          {view === 'about' ? <AboutPage health={health} /> : null}
        </main>

        <footer className="border-t border-line-soft px-4 py-4 sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-2 text-[11.5px] text-faint">
            <p>
              <span className="font-medium uppercase tracking-[0.16em] text-muted">Glint</span>
              <span className="mx-2 text-line">·</span>
              See beyond the page.
            </p>
            <p>
              Local OCR with RapidOCR {health?.ocr.engine_version ?? ''} on ONNX Runtime{' '}
              {health?.ocr.runtime_version ?? ''} — no cloud, no GPU, no account.
            </p>
          </div>
        </footer>
      </div>
    </div>
  )
}
