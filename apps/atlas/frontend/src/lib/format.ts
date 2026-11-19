/** Arabic formatting helpers (Gregorian calendar, Latin digits — easiest to scan). */

const dateFmt = new Intl.DateTimeFormat('ar-EG-u-ca-gregory-nu-latn', {
  day: '2-digit',
  month: 'short',
})
const dateYearFmt = new Intl.DateTimeFormat('ar-EG-u-ca-gregory-nu-latn', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})
const timeFmt = new Intl.DateTimeFormat('ar-EG-u-ca-gregory-nu-latn', {
  hour: '2-digit',
  minute: '2-digit',
})

export function shortDate(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const now = new Date()
  return d.getFullYear() === now.getFullYear() ? dateFmt.format(d) : dateYearFmt.format(d)
}

export function dateTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${dateYearFmt.format(d)} · ${timeFmt.format(d)}`
}

export function relativeTime(iso?: string | null): string {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const diff = Math.round((Date.now() - then) / 1000)
  if (diff < 45) return 'دلوقتي'
  const mins = Math.round(diff / 60)
  if (mins < 60) return `قبل ${mins} دقيقة`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `قبل ${hours} ساعة`
  const days = Math.round(hours / 24)
  if (days < 30) return `قبل ${days} يوم`
  const months = Math.round(days / 30)
  if (months < 12) return `قبل ${months} شهر`
  return `قبل ${Math.round(months / 12)} سنة`
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '؟'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

/** Net-new position for an item dropped between two neighbours (sparse floats). */
export function positionBetween(prev?: number | null, next?: number | null): number {
  if (prev == null && next == null) return 1024
  if (prev == null) return (next as number) - 1024
  if (next == null) return (prev as number) + 1024
  return (prev + next) / 2
}
