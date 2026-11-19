import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { STATUS_ORDER, type TicketOut, type TicketStatus } from '../api/types'
import { Avatar, EmptyState, ErrorBox, PriorityChip, Spinner, StatusChip } from '../components/ui'
import { relativeTime } from '../lib/format'
import { useAsync } from '../lib/useAsync'

export function MyWorkScreen() {
  const navigate = useNavigate()
  const work = useAsync(() => api.myWork(), [])

  const grouped = useMemo(() => {
    const map = new Map<TicketStatus, TicketOut[]>()
    for (const status of STATUS_ORDER) map.set(status, [])
    for (const ticket of work.data?.assigned ?? []) {
      const bucket = map.get(ticket.status)
      if (bucket) bucket.push(ticket)
    }
    return map
  }, [work.data])

  const assigned = work.data?.assigned ?? []
  const mentions = work.data?.mentions ?? []
  const open = assigned.filter((t) => t.status !== 'done').length

  if (work.loading && !work.data) return <Spinner label="بيحمّل شغلك…" />
  if (work.error) return <ErrorBox message={work.error.message} onRetry={work.reload} />

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-bold text-slate-100">شغلي</h1>
        <p className="mt-0.5 text-xs text-slate-400">
          {open} تذكرة مفتوحة · {mentions.length} منشن جديد
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-slate-200">تذاكري</h2>
        {assigned.length === 0 ? (
          <EmptyState icon="🎉" title="مفيش تذاكر متعيّنة عليك" hint="كل حاجة خلصت — أو لسه محدش وزّع شغل." />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {STATUS_ORDER.filter((s) => (grouped.get(s) ?? []).length > 0).map((status) => (
              <div key={status} className="card p-3">
                <div className="mb-2 flex items-center justify-between">
                  <StatusChip status={status} />
                  <span className="text-[11px] text-slate-500">{grouped.get(status)?.length}</span>
                </div>
                <ul className="space-y-1.5">
                  {(grouped.get(status) ?? []).map((ticket) => (
                    <li key={ticket.id}>
                      <Link
                        to={`/p/${ticket.project_key}/t/${ticket.key}`}
                        className="block rounded-lg border border-white/6 bg-white/3 px-2.5 py-2 transition hover:border-white/12 hover:bg-white/6"
                      >
                        <span className="line-clamp-2 text-xs text-slate-100">{ticket.title}</span>
                        <span className="mt-1 flex items-center gap-2">
                          <span className="font-mono text-[10px] text-slate-500">{ticket.key}</span>
                          <PriorityChip priority={ticket.priority} />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-slate-200">منشنز لسه مقريتهاش</h2>
        {mentions.length === 0 ? (
          <EmptyState icon="🔔" title="مفيش منشن جديد" hint="لما حد يعمل @لك في كومنت هتلاقيه هنا." />
        ) : (
          <ul className="space-y-1.5">
            {mentions.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  className="flex w-full items-center gap-2.5 rounded-xl border border-white/8 bg-white/3 px-3 py-2 text-start transition hover:bg-white/6"
                  onClick={() => {
                    if (m.ticket_key) navigate(`/t/${m.ticket_key}`)
                    void api.markRead(m.id).then(() => work.reload())
                  }}
                >
                  <Avatar user={m.actor ?? null} size={24} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs text-slate-200">{m.message}</span>
                    <span className="mt-0.5 block text-[10px] text-slate-500">
                      {m.ticket_key ?? ''} · {relativeTime(m.created_at)}
                    </span>
                  </span>
                  <span className="size-1.5 shrink-0 rounded-full bg-brand-400" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
