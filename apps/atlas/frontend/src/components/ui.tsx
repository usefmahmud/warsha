import type { ReactNode } from 'react'
import { useEffect } from 'react'
import {
  PRIORITY_LABEL,
  PRIORITY_STYLE,
  STATUS_LABEL,
  STATUS_STYLE,
  TYPE_LABEL,
  type TicketPriority,
  type TicketStatus,
  type TicketType,
  type UserBrief,
} from '../api/types'
import { initials } from '../lib/format'

export function Avatar({ user, size = 28 }: { user?: UserBrief | null; size?: number }) {
  const style = { width: size, height: size, backgroundColor: user?.color ?? '#475569' }
  if (!user) {
    return (
      <span
        className="inline-grid shrink-0 place-items-center rounded-full text-[11px] font-bold text-white/80 ring-1 ring-white/10"
        style={style}
        title="مش متعيّن"
      >
        —
      </span>
    )
  }
  if (user.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={user.full_name || user.username}
        className="shrink-0 rounded-full object-cover ring-1 ring-white/15"
        style={style}
        title={user.full_name || user.username}
      />
    )
  }
  return (
    <span
      className="inline-grid shrink-0 place-items-center rounded-full text-[11px] font-bold text-white ring-1 ring-white/15"
      style={{ ...style, fontSize: Math.max(10, size * 0.4) }}
      title={user.full_name || user.username}
    >
      {initials(user.full_name || user.username)}
    </span>
  )
}

export function StatusChip({ status }: { status: TicketStatus }) {
  return <span className={`chip ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>
}

export function PriorityChip({ priority }: { priority: TicketPriority }) {
  return <span className={`chip ${PRIORITY_STYLE[priority]}`}>{PRIORITY_LABEL[priority]}</span>
}

export function TypeChip({ type }: { type: TicketType }) {
  return <span className="chip border-white/10 bg-white/5 text-slate-300">{TYPE_LABEL[type]}</span>
}

export function Spinner({ label = 'بيحمّل…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-sm text-slate-400">
      <span className="size-4 animate-spin rounded-full border-2 border-slate-500 border-t-transparent" />
      {label}
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
      <div className="flex items-center justify-between gap-3">
        <span>{message}</span>
        {onRetry && (
          <button type="button" className="btn-ghost !py-1 !text-xs" onClick={onRetry}>
            حاول تاني
          </button>
        )}
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  icon = '📋',
  action,
}: {
  title: string
  hint?: string
  icon?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-white/10 px-6 py-12 text-center">
      <span className="text-3xl">{icon}</span>
      <p className="text-sm font-medium text-slate-200">{title}</p>
      {hint && <p className="max-w-sm text-xs text-slate-400">{hint}</p>}
      {action}
    </div>
  )
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-ink-850 p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100">{title}</h2>
          <button type="button" className="btn-ghost !px-2 !py-1" onClick={onClose} aria-label="إغلاق">
            ✕
          </button>
        </div>
        <div className="space-y-3">{children}</div>
        {footer && <div className="mt-5 flex items-center justify-end gap-2">{footer}</div>}
      </div>
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-slate-300">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-slate-500">{hint}</span>}
    </label>
  )
}
