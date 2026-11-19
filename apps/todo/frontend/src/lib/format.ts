import type { Priority, Todo } from '../types'

export const PRIORITY_META: Record<Priority, { label: string; chip: string }> = {
  high: {
    label: 'عالية',
    chip: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  },
  normal: {
    label: 'عادية',
    chip: 'border-brand-400/40 bg-brand-500/10 text-brand-300',
  },
  low: {
    label: 'منخفضة',
    chip: 'border-slate-500/40 bg-slate-500/10 text-slate-400',
  },
}

export const PRIORITY_ORDER: Record<Priority, number> = { high: 0, normal: 1, low: 2 }

export function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return new Intl.DateTimeFormat('ar-EG', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

/** Human, RTL-friendly due label with an overdue flag. */
export function formatDue(value: string | null): { label: string; overdue: boolean } | null {
  if (!value) return null
  const due = new Date(`${value}T00:00:00`)
  if (Number.isNaN(due.getTime())) return null

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diffDays = Math.round((due.getTime() - today.getTime()) / 86_400_000)

  const overdue = diffDays < 0
  let label: string
  if (diffDays === 0) label = 'النهاردة'
  else if (diffDays === 1) label = 'بكرة'
  else if (diffDays === -1) label = 'فاتت (امبارح)'
  else {
    const formatted = new Intl.DateTimeFormat('ar-EG', {
      day: 'numeric',
      month: 'short',
    }).format(due)
    label = overdue ? `فاتت (${formatted})` : formatted
  }
  return { label, overdue }
}

export function plural(n: number): string {
  if (n === 0) return 'ولا حاجة'
  if (n === 1) return 'واحدة'
  if (n === 2) return 'اتنين'
  if (n <= 10) return `${n} مهام`
  return `${n} مهمة`
}

export function sortTodos(items: Todo[]): Todo[] {
  return [...items].sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1
    const p = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
    if (p !== 0) return p
    return b.created_at.localeCompare(a.created_at)
  })
}
