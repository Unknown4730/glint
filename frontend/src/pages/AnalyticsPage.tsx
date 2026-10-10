import { useCallback, useEffect, useState } from 'react'
import {
  BarChart3,
  Clock3,
  FileStack,
  FileText,
  Hash,
  RefreshCw,
  Timer,
} from 'lucide-react'
import type { Analytics } from '../types'
import { ApiError, api } from '../services/api'
import { useToast } from '../hooks/useToast'
import { formatDateTime, formatDuration, formatNumber, fileTypeLabel } from '../lib/format'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { Panel } from '../components/Panel'
import { Spinner } from '../components/Spinner'
import { StatCard } from '../components/StatCard'

export interface AnalyticsPageProps {
  refreshKey: number
  onNavigateWorkspace: () => void
}

export function AnalyticsPage({ refreshKey, onNavigateWorkspace }: AnalyticsPageProps) {
  const { push } = useToast()
  const [data, setData] = useState<Analytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [chartKey, setChartKey] = useState(() => Date.now())
  const [chartState, setChartState] = useState<'loading' | 'ready' | 'failed'>('loading')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const summary = await api.analytics()
      setData(summary)
      setChartKey(Date.now())
      setChartState('loading')
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Analytics could not be computed from the local history.',
      )
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-ink">
            Analytics
          </h1>
          <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-muted">
            Aggregated from the saved history with pandas, and drawn as one matplotlib chart.
            Nothing here is estimated — with an empty database you simply see an empty state.
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            void load()
            push({ tone: 'info', title: 'Analytics refreshed' })
          }}
          icon={<RefreshCw />}
          loading={loading}
        >
          Refresh
        </Button>
      </div>

      {error ? (
        <Alert tone="error" title="Analytics unavailable" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      ) : null}

      {loading && !data ? (
        <Panel>
          <div className="flex items-center justify-center gap-2.5 py-14 text-[13px] text-muted">
            <Spinner className="h-4 w-4 text-lime" />
            Reading the processing history…
          </div>
        </Panel>
      ) : !data || !data.has_data ? (
        <Panel>
          <EmptyState
            icon={<BarChart3 />}
            title="No statistics yet"
            description="Glint has not processed a document yet, so there is nothing honest to show. Extract one document and these numbers are computed from your real history."
            action={
              <Button variant="primary" size="sm" onClick={onNavigateWorkspace}>
                Go to the Workspace
              </Button>
            }
          />
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Documents"
              value={formatNumber(data.total_documents)}
              hint={
                data.last_processed_at
                  ? `last ${formatDateTime(data.last_processed_at)}`
                  : 'no jobs yet'
              }
              icon={<FileText />}
            />
            <StatCard
              label="Pages"
              value={formatNumber(data.total_pages)}
              hint={`${(data.total_pages / Math.max(1, data.total_documents)).toFixed(1)} pages per document`}
              icon={<FileStack />}
            />
            <StatCard
              label="Avg. duration"
              value={formatDuration(data.average_duration_ms)}
              hint={`fastest ${formatDuration(data.fastest_duration_ms)} · slowest ${formatDuration(
                data.slowest_duration_ms,
              )}`}
              icon={<Clock3 />}
            />
            <StatCard
              label="Most used type"
              value={
                data.most_common_file_type ? fileTypeLabel(data.most_common_file_type) : '—'
              }
              hint={
                data.most_common_file_type
                  ? `${formatNumber(data.file_type_counts[data.most_common_file_type] ?? 0)} of ${formatNumber(
                      data.total_documents,
                    )} documents`
                  : 'no data'
              }
              icon={<Timer />}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
            <Panel
              title="Processing activity"
              subtitle="Generated on the backend with matplotlib (Agg backend, no GUI)."
              icon={<BarChart3 />}
            >
              {chartState === 'failed' ? (
                <Alert tone="warning" title="The chart could not be loaded">
                  The metrics above are still correct — only the image failed to render.
                </Alert>
              ) : (
                <div className="relative">
                  {chartState === 'loading' ? (
                    <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 text-[12.5px] text-muted">
                      <Spinner className="h-4 w-4 text-lime" />
                      Drawing chart…
                    </div>
                  ) : null}
                  <img
                    key={chartKey}
                    src={api.chartUrl(chartKey)}
                    alt="Bar chart of documents processed per day and file type distribution"
                    className={`w-full rounded-lg border border-line bg-canvas transition-opacity duration-300 ${
                      chartState === 'ready' ? 'opacity-100' : 'opacity-25'
                    }`}
                    onLoad={() => setChartState('ready')}
                    onError={() => setChartState('failed')}
                  />
                </div>
              )}
            </Panel>

            <Panel title="Breakdown" subtitle="Real counts from SQLite" icon={<Hash />}>
              <dl className="space-y-2.5">
                {Object.entries(data.file_type_counts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([type, count]) => {
                    const share =
                      data.total_documents > 0 ? Math.round((count / data.total_documents) * 100) : 0
                    return (
                      <div key={type}>
                        <div className="flex items-baseline justify-between gap-2 text-[12.5px]">
                          <dt className="font-medium text-ink">{fileTypeLabel(type)}</dt>
                          <dd className="tabular-nums text-muted">
                            {count} · {share}%
                          </dd>
                        </div>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-raised">
                          <div
                            className="h-full rounded-full bg-lime/80 transition-all duration-500"
                            style={{ width: `${Math.max(3, share)}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
              </dl>

              <div className="mt-4 border-t border-line-soft pt-3.5 text-[12.5px]">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-muted">Total characters</span>
                  <span className="font-medium tabular-nums text-ink">
                    {formatNumber(data.total_characters)}
                  </span>
                </div>
                <div className="mt-1.5 flex items-baseline justify-between gap-2">
                  <span className="text-muted">Avg. per document</span>
                  <span className="font-medium tabular-nums text-ink">
                    {formatNumber(
                      Math.round(data.total_characters / Math.max(1, data.total_documents)),
                    )}
                  </span>
                </div>
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}
