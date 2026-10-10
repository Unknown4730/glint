import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Copy text to the clipboard with a short "Copied" feedback state.
 *
 * Uses the async Clipboard API when it is available and falls back to a hidden
 * textarea + execCommand, because the clipboard API is restricted in some
 * browsers and in non-secure contexts.
 */
export function useClipboard(resetAfterMs = 2000) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    }
  }, [])

  const flash = useCallback(() => {
    setCopied(true)
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setCopied(false), resetAfterMs)
  }, [resetAfterMs])

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text) return false

      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text)
          flash()
          return true
        }
      } catch {
        // fall through to the legacy path
      }

      try {
        const area = document.createElement('textarea')
        area.value = text
        area.setAttribute('readonly', '')
        area.style.position = 'fixed'
        area.style.top = '-1000px'
        area.style.opacity = '0'
        document.body.appendChild(area)
        area.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(area)
        if (ok) flash()
        return ok
      } catch {
        return false
      }
    },
    [flash],
  )

  return { copied, copy }
}
