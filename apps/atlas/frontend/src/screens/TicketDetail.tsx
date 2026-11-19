import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  PRIORITY_LABEL,
  STATUS_LABEL,
  STATUS_ORDER,
  type ActivityOut,
  type CommentOut,
  type MemberOut,
  type TicketPriority,
  type TicketStatus,
} from '../api/types'
import { errorMessage } from '../auth'
import { CommentComposer } from '../components/CommentComposer'
import { Avatar, ErrorBox, PriorityChip, Spinner, StatusChip, TypeChip } from '../components/ui'
import { dateTime, relativeTime, shortDate } from '../lib/format'
import { useAsync } from '../lib/useAsync'

type Tab = 'comments' | 'activity'

function HighlightedBody({ body, usernames }: { body: string; usernames: Set<string> }) {
  const parts = body.split(/(@[A-Za-z0-9_.-]+)/g)
  return (
    <p className="text-[13px] leading-6 whitespace-pre-wrap text-slate-200">
      {parts.map((part, i) => {
        if (part.startsWith('@') && usernames.has(part.slice(1).toLowerCase())) {
          return (
            <span key={i} className="rounded bg-brand-500/20 px-1 font-medium text-brand-200">
              {part}
            </span>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </p>
  )
}

function ActivityRow({ event }: { event: ActivityOut }) {
  const detail =
    event.field && (event.old_value || event.new_value)
      ? `${event.field}: ${event.old_value ?? '—'} → ${event.new_value ?? '—'}`
      : event.new_value ?? ''
  return (
    <li className="flex items-start gap-2.5 py-2">
      <Avatar user={event.actor ?? null} size={22} />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-300">
          <span className="font-medium text-slate-100">{event.actor?.full_name ?? 'النظام'}</span>{' '}
          <span className="text-slate-400">{event.action}</span>{' '}
          {detail && <span className="font-mono text-[11px] text-slate-400">{detail}</span>}
        </p>
        <p className="mt-0.5 text-[10px] text-slate-500">{relativeTime(event.created_at)}</p>
      </div>
    </li>
  )
}

export function TicketScreen() {
  const { projectKey: routeProjectKey, ticketKey = '' } = useParams()
  const [tab, setTab] = useState<Tab>('comments')
  const [error, setError] = useState<string | null>(null)
  const [savingStatus, setSavingStatus] = useState(false)

  const ticket = useAsync(() => api.ticket(ticketKey), [ticketKey])
  const projectKey = routeProjectKey ?? ticket.data?.project_key ?? ''

  const comments = useAsync(() => api.comments(ticketKey), [ticketKey])
  const activity = useAsync(() => api.activity(ticketKey), [ticketKey])
  const members = useAsync(() => (projectKey ? api.members(projectKey).catch(() => [] as MemberOut[]) : Promise.resolve([] as MemberOut[])), [projectKey])

  const usernames = useMemo(
    () => new Set((members.data ?? []).map((m) => m.user.username.toLowerCase())),
    [members.data],
  )

  async function changeStatus(status: TicketStatus) {
    setSavingStatus(true)
    setError(null)
    try {
      await api.transition(ticketKey, status)
      ticket.reload()
      activity.reload()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSavingStatus(false)
    }
  }

  async function changePriority(priority: TicketPriority) {
    setError(null)
    try {
      await api.updateTicket(ticketKey, { priority })
      ticket.reload()
      activity.reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function addComment(body: string) {
    await api.addComment(ticketKey, body)
    comments.reload()
    activity.reload()
    ticket.reload()
  }

  if (ticket.loading && !ticket.data) return <Spinner label="بيحمّل التذكرة…" />
  if (ticket.error) return <ErrorBox message={ticket.error.message} onRetry={ticket.reload} />
  const t = ticket.data
  if (!t) return null

  const commentItems = comments.data?.items ?? []
  const activityItems = activity.data?.items ?? []

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <nav className="flex items-center gap-1.5 text-[11px] text-slate-500">
        <Link to="/projects" className="hover:text-slate-300">المشاريع</Link>
        <span>/</span>
        <Link to={`/p/${projectKey}/board`} className="hover:text-slate-300">{projectKey}</Link>
        <span>/</span>
        <span className="font-mono text-slate-300">{t.key}</span>
      </nav>

      <header className="card space-y-3 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-lg leading-snug font-bold text-slate-100">{t.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <StatusChip status={t.status} />
              <PriorityChip priority={t.priority} />
              <TypeChip type={t.type} />
              {(t.labels ?? []).map((label) => (
                <span
                  key={label.id}
                  className="chip border-transparent"
                  style={{ backgroundColor: `${label.color}22`, color: label.color }}
                >
                  {label.name}
                </span>
              ))}
              {t.parent_key && (
                <Link to={`/t/${t.parent_key}`} className="chip border-white/10 bg-white/5 text-slate-300">
                  ⤴ {t.parent_key}
                </Link>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              className="input !w-auto !py-1.5 text-xs"
              value={t.status}
              disabled={savingStatus}
              onChange={(e) => changeStatus(e.target.value as TicketStatus)}
              aria-label="تغيير الحالة"
            >
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>{STATUS_LABEL[s]}</option>
              ))}
            </select>
            <select
              className="input !w-auto !py-1.5 text-xs"
              value={t.priority}
              onChange={(e) => changePriority(e.target.value as TicketPriority)}
              aria-label="تغيير الأولوية"
            >
              {(Object.keys(PRIORITY_LABEL) as TicketPriority[]).map((p) => (
                <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <p className="rounded-lg border border-rose-400/20 bg-rose-500/10 px-2.5 py-1.5 text-[11px] text-rose-200">
            {error}
          </p>
        )}

        <dl className="grid grid-cols-2 gap-3 border-t border-white/8 pt-3 text-[11px] sm:grid-cols-4">
          <div>
            <dt className="text-slate-500">المسؤول</dt>
            <dd className="mt-1 flex items-center gap-1.5 text-slate-200">
              <Avatar user={t.assignee ?? null} size={20} />
              {t.assignee?.full_name ?? 'مش متعيّن'}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">الكاتب</dt>
            <dd className="mt-1 flex items-center gap-1.5 text-slate-200">
              <Avatar user={t.reporter ?? null} size={20} />
              {t.reporter?.username ?? '—'}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">الاستحقاق</dt>
            <dd className="mt-1 text-slate-200">{shortDate(t.due_date)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">آخر تحديث</dt>
            <dd className="mt-1 text-slate-200" title={dateTime(t.updated_at)}>{relativeTime(t.updated_at)}</dd>
          </div>
        </dl>
      </header>

      {t.description && (
        <section className="card p-4">
          <h2 className="mb-2 text-xs font-semibold text-slate-300">الوصف</h2>
          <HighlightedBody body={t.description} usernames={usernames} />
        </section>
      )}

      <section className="card p-4">
        <div className="mb-3 flex items-center gap-1 text-[11px]">
          <button
            type="button"
            className={`rounded-lg px-2.5 py-1 ${tab === 'comments' ? 'bg-white/10 text-slate-100' : 'text-slate-400 hover:bg-white/6'}`}
            onClick={() => setTab('comments')}
          >
            كومنتات · {commentItems.length}
          </button>
          <button
            type="button"
            className={`rounded-lg px-2.5 py-1 ${tab === 'activity' ? 'bg-white/10 text-slate-100' : 'text-slate-400 hover:bg-white/6'}`}
            onClick={() => setTab('activity')}
          >
            النشاط · {activityItems.length}
          </button>
        </div>

        {tab === 'comments' ? (
          <div className="space-y-3">
            {comments.loading && !comments.data && <Spinner label="بيحمّل الكومنتات…" />}
            {commentItems.length === 0 && !comments.loading && (
              <p className="rounded-xl border border-dashed border-white/10 py-6 text-center text-[11px] text-slate-500">
                مفيش كومنتات لسه — ابدأ النقاش.
              </p>
            )}
            <ul className="space-y-3">
              {commentItems.map((comment: CommentOut) => (
                <li key={comment.id} className="rounded-xl border border-white/8 bg-white/3 p-3">
                  <div className="mb-1.5 flex items-center gap-2">
                    <Avatar user={comment.author} size={22} />
                    <span className="text-xs font-medium text-slate-200">{comment.author.full_name || comment.author.username}</span>
                    <span className="text-[10px] text-slate-500" title={dateTime(comment.created_at)}>
                      {relativeTime(comment.created_at)}
                    </span>
                    {comment.edited && <span className="text-[10px] text-slate-600">(معدّل)</span>}
                  </div>
                  <HighlightedBody body={comment.body} usernames={usernames} />
                </li>
              ))}
            </ul>
            <div className="border-t border-white/8 pt-3">
              <CommentComposer members={members.data ?? []} onSubmit={addComment} />
            </div>
          </div>
        ) : (
          <div>
            {activity.loading && !activity.data && <Spinner label="بيحمّل النشاط…" />}
            {activityItems.length === 0 && !activity.loading && (
              <p className="py-6 text-center text-[11px] text-slate-500">مفيش نشاط مسجّل.</p>
            )}
            <ul className="divide-y divide-white/6">
              {activityItems.map((event) => (
                <ActivityRow key={event.id} event={event} />
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
