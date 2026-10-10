import { useCallback, useEffect, useState } from 'react'
import {
  Clock3,
  Database,
  ExternalLink,
  History as HistoryIcon,
  Search,
  SearchX,
  Trash2,
  X,
} from 'lucide-react'
import type { HistoryItem, OCRResult } from '../types'
import { ApiError, api } from '../services/api'
import { useToast } from '../hooks/useToast'
import { formatDateTime, formatDuration, formatNumber, formatRelative } from '../lib/format'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EmptyState } from '../components/EmptyState'
import { FileTypeBadge } from '../components/Badge'
import { Panel } from '../components/Panel'
import { Spinner } from '../components/Spinner'

export interface HistoryPageProps {
  onOpenResult: (result: OCRResult) => void
  refreshKey: number
}

export function HistoryPage({ onOpenResult, refreshKey }: HistoryPageProps) {
  const { push } = useToast()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [openingId, setOpeningId] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<HistoryItem | null>(null)
  const [confirmClear, setConfirmClear] = useState(false)
  const [busy, setBusy] = useState(false)

  // Debounce the search box so SQLite is not hammered on every keystroke.
  useEffect(() => {
    const handle = window.setTimeout(() => setSearch(searchInput.trim()), 250)
    return () => window.clearTimeout(handle)
  }, [searchInput])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.history(search)
      setItems(response.items)
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'The history could not be loaded from the local database.',
      )
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  const openItem = async (item: HistoryItem) => {
    setOpeningId(item.id)
    try {
      const detail = await api.historyItem(item.id)
      onOpenResult(detail)
    } catch (caught) {
      const message =
        caught instanceof ApiError ? caught.message : 'This record could not be opened.'
      push({ tone: 'error', title: 'Could not open the result', description: message })
      if (caught instanceof ApiError && caught.status === 404) void load()
    } finally {
      setOpeningId(null)
    }
  }

  const deleteItem = async () => {
    if (!pendingDelete) return
    setBusy(true)
    try {
      await api.deleteHistoryItem(pendingDelete.id)
      push({ tone: 'success', title: 'History entry deleted', description: pendingDelete.filename })
      setPendingDelete(null)
      void load()
    } catch (caught) {
      push({
        tone: 'error',
        title: 'Delete failed',
        description: caught instanceof ApiError ? caught.message : 'Unexpected error.',
      })
    } finally {
      setBusy(false)
    }
  }

  const clearAll = async () => {
    setBusy(true)
    try {
      const response = await api.clearHistory()
      push({
        tone: 'success',
        title: 'History cleared',
        description: `${response.deleted_count} record(s) removed from SQLite.`,
      })
      setConfirmClear(false)
      void load()
    } catch (caught) {
      push({
        tone: 'error',
        title: 'Could not clear history',
        description: caught instanceof ApiError ? caught.message : 'Unexpected error.',
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-ink">
            History
          </h1>
          <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-muted">
            Every finished job is stored in a local SQLite database — extracted text and metadata
            only. Original documents are never kept.
          </p>
        </div>
        <Button
          variant="danger"
          size="sm"
          onClick={() => setConfirmClear(true)}
          disabled={items.length === 0 || loading}
          icon={<Trash2 />}
        >
          Clear history
        </Button>
      </div>

      {error ? (
        <Alert tone="error" title="History could not be loaded" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      ) : null}

      <Panel
        title={`Processing history${items.length ? ` · ${items.length}` : ''}`}
        subtitle="Open a record to read its text again, or delete it permanently."
        icon={<HistoryIcon />}
        bodyClassName="px-0 py-0"
        actions={
          <label className="relative flex items-center">
            <Search
              className="pointer-events-none absolute left-2.5 h-4 w-4 text-faint"
              aria-hidden="true"
            />
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search filename…"
              aria-label="Search history by filename"
              className="h-9 w-[13.5rem] rounded-lg border border-line bg-raised pl-8.5 pr-8 text-[13px] text-ink placeholder:text-faint focus:border-lime/50 focus:outline-none"
            />
            {searchInput ? (
              <button
                type="button"
                onClick={() => setSearchInput('')}
                className="absolute right-2 rounded p-0.5 text-faint transition hover:text-ink"
                aria-label="Clear search"
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            ) : null}
          </label>
        }
      >
        {loading ? (
          <div className="flex items-center justify-center gap-2.5 px-5 py-14 text-[13px] text-muted">
            <Spinner className="h-4 w-4 text-lime" />
            Loading history from SQLite…
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={search ? <SearchX /> : <Database />}
            title={search ? `No result matches “${search}”` : 'No documents processed yet'}
            description={
              search
                ? 'Try a different part of the filename, or clear the search to see everything.'
                : 'Once you extract text in the Workspace, every job appears here with its page count, duration and character count.'
            }
            action={
              search ? (
                <Button size="sm" onClick={() => setSearchInput('')}>
                  Clear search
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y divide-line-soft">
            {items.map((item) => (
              <li
                key={item.id}
                className="group flex flex-wrap items-center gap-3 px-5 py-3.5 transition-colors hover:bg-raised/45 sm:flex-nowrap"
              >
                <span className="shrink-0">
                  <FileTypeBadge fileType={item.file_type} />
                </span>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-medium text-ink" title={item.filename}>
                    {item.filename}
                  </p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11.5px] text-muted">
                    <span title={formatDateTime(item.created_at)}>
                      {formatRelative(item.created_at)}
                    </span>
                    <span className="text-line">·</span>
                    <span>{item.pages} page{item.pages === 1 ? '' : 's'}</span>
                    <span className="text-line">·</span>
                    <span className="inline-flex items-center gap-1">
                      <Clock3 className="h-3 w-3" aria-hidden="true" />
                      {formatDuration(item.duration_ms)}
                    </span>
                    <span className="text-line">·</span>
                    <span className="tabular-nums">{formatNumber(item.char_count)} chars</span>
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void openItem(item)}
                    loading={openingId === item.id}
                    icon={<ExternalLink />}
                  >
                    Open
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setPendingDelete(item)}
                    aria-label={`Delete ${item.filename}`}
                    title="Delete this record"
                    className="hover:text-danger"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this history entry?"
        description={
          <>
            <span className="font-medium text-ink">{pendingDelete?.filename}</span> and its
            extracted text will be removed from the local database. This cannot be undone.
          </>
        }
        confirmLabel="Delete entry"
        busy={busy}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void deleteItem()}
      />

      <ConfirmDialog
        open={confirmClear}
        title="Clear the whole history?"
        description="Every saved job, including all extracted text, will be deleted from the local SQLite database. This cannot be undone."
        confirmLabel={`Delete ${items.length} record${items.length === 1 ? '' : 's'}`}
        busy={busy}
        onCancel={() => setConfirmClear(false)}
        onConfirm={() => void clearAll()}
      />
    </div>
  )
}
