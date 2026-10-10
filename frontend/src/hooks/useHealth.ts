import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'
import type { Health } from '../types'

interface HealthState {
  health: Health | null
  loading: boolean
  error: ApiError | null
  refresh: () => Promise<void>
}

/**
 * Loads GET /api/health once on mount.
 *
 * The result drives the "local processing" status pill in the sidebar and the
 * honest warning banner when the OCR engine is not ready.
 */
export function useHealth(): HealthState {
  const [health, setHealth] = useState<Health | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const result = await api.health()
      setHealth(result)
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : new ApiError(String(caught), 'unknown', 0))
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { health, loading, error, refresh }
}
