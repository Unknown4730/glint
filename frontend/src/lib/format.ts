/** Small formatting helpers shared by every screen. */

export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return '0 ms'
  if (ms < 1000) return `${Math.round(ms)} ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 2 : 1)} s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return `${minutes} m ${String(rest).padStart(2, '0')} s`
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** exponent
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined).format(value)
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function formatRelative(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const diffMs = Date.now() - date.getTime()
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} d ago`
  return formatDateTime(iso)
}

/** "jpeg" -> "JPG", "pdf" -> "PDF" */
export function fileTypeLabel(fileType: string): string {
  const value = (fileType || '').toLowerCase()
  if (value === 'jpeg') return 'JPG'
  return value.toUpperCase()
}

/** Safe download name built from the original filename. */
export function textFileNameFor(originalFilename: string): string {
  const base = originalFilename.replace(/\.[^.]+$/, '').replace(/[^\w\-. ]+/g, '_').trim()
  return `${base || 'glint-result'}-ocr.txt`
}
