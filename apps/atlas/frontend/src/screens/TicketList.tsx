import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  PRIORITY_LABEL,
  STATUS_LABEL,
  STATUS_ORDER,
  type MemberOut,
  type TicketPriority,
  type TicketStatus,
} from '../api/types'
import { NewTicketModal } from '../components/NewTicketModal'
import { Avatar, EmptyState, ErrorBox, PriorityChip, StatusChip, Spinner } from '../components/ui'
import { relativeTime } from '../lib/format'
import { useAsync } from '../lib/useAsync'

export function ListScreen() {
  const { projectKey = '' } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<TicketStatus | ''>('')
  const [priority, setPriority] = useState<TicketPriority | ''>('')
  const [assignee, setAssignee] = useState('')
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [creating, setCreating] = useState(false)
  const [sort, setSort] = useState('updated_at')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(search.trim()), 300)
    return () => window.clearTimeout(id)
  }, [search])

  const tickets = useAsync(
    () => api.projectTickets(projectKey, { status, priority, assignee, q: debounced, limit: 100, sort, order }),
    [projectKey, status, priority, assignee, debounced, sort, order],
  )
  const members = useAsync(() => api.members(projectKey).catch(() => [] as MemberOut[]), [projectKey])
  const list = useMemo(() => members.data ?? [], [members.data])

  function toggleSort(field: string) {
    if (sort === field) setOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    else {
      setSort(field)
      setOrder('desc')
    }
  }

  const rows = tickets.data?.items ?? []

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-bold text-slate-100">تذاكر {projectKey}</h1>
          <div className="mt-1 flex items-center gap-1 text-[11px]">
            <Link to={`/p/${projectKey}/board`} className="rounded-md px-2 py-0.5 text-slate-400 hover:bg-white/6">
              بورد
            </Link>
            <Link to={`/p/${projectKey}/list`} className="rounded-md bg-white/8 px-2 py-0.5 text-slate-200">
              ليستة
            </Link>
          </div>
        </div>
        <button type="button" className="btn-primary !py-1.5" onClick={() => setCreating(true)}>
          + تذكرة
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <input
          className="input !w-56 !py-1.5 text-xs"
          placeholder="بحث بالعنوان أو الوصف…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="input !w-auto !py-1.5 text-xs" value={status} onChange={(e) => setStatus(e.target.value as TicketStatus | '')}>
          <option value="">كل الحالات</option>
          {STATUS_ORDER.map((s) => (
            <option key={s} value={s}>{STATUS_LABEL[s]}</option>
          ))}
        </select>
        <select className="input !w-auto !py-1.5 text-xs" value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority | '')}>
          <option value="">كل الأولويات</option>
          {(Object.keys(PRIORITY_LABEL) as TicketPriority[]).map((p) => (
            <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>
          ))}
        </select>
        <select className="input !w-auto !py-1.5 text-xs" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
          <option value="">كل المسؤولين</option>
          {list.map((m) => (
            <option key={m.user.id} value={m.user.username}>{m.user.full_name || m.user.username}</option>
          ))}
        </select>
        {tickets.data && <span className="text-[11px] text-slate-500">{tickets.data.total} نتيجة</span>}
      </div>

      {tickets.loading && !tickets.data && <Spinner />}
      {tickets.error && <ErrorBox message={tickets.error.message} onRetry={tickets.reload} />}

      {!tickets.loading && !tickets.error && rows.length === 0 && (
        <EmptyState title="مفيش تذاكر مطابقة" hint="جرّب تغيّر الفلاتر أو تضيف تذكرة جديدة." icon="🔍" />
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-white/8">
          <table className="w-full min-w-[720px] text-start text-xs">
            <thead className="bg-white/4 text-[11px] text-slate-400">
              <tr>
                <th className="px-3 py-2 text-start font-medium">المفتاح</th>
                <th className="px-3 py-2 text-start font-medium">العنوان</th>
                <th className="px-3 py-2 text-start font-medium">الحالة</th>
                <th className="px-3 py-2 text-start font-medium">الأولوية</th>
                <th className="px-3 py-2 text-start font-medium">المسؤول</th>
                <th className="px-3 py-2 text-start font-medium">
                  <button type="button" className="hover:text-slate-200" onClick={() => toggleSort('updated_at')}>
                    آخر تحديث {sort === 'updated_at' ? (order === 'asc' ? '↑' : '↓') : ''}
                  </button>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/6">
              {rows.map((t) => (
                <tr
                  key={t.id}
                  className="cursor-pointer transition hover:bg-white/4"
                  onClick={() => navigate(`/p/${projectKey}/t/${t.key}`)}
                >
                  <td className="px-3 py-2 font-mono text-[11px] whitespace-nowrap text-slate-400">{t.key}</td>
                  <td className="max-w-[340px] px-3 py-2">
                    <span className="line-clamp-1 text-slate-100">{t.title}</span>
                    <span className="mt-0.5 flex gap-1">
                      {(t.labels ?? []).map((l) => (
                        <span key={l.id} className="chip border-transparent" style={{ backgroundColor: `${l.color}22`, color: l.color }}>
                          {l.name}
                        </span>
                      ))}
                    </span>
                  </td>
                  <td className="px-3 py-2"><StatusChip status={t.status} /></td>
                  <td className="px-3 py-2"><PriorityChip priority={t.priority} /></td>
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-1.5">
                      <Avatar user={t.assignee ?? null} size={20} />
                      <span className="text-slate-300">{t.assignee?.username ?? '—'}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-slate-500">{relativeTime(t.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NewTicketModal
        open={creating}
        projectKey={projectKey}
        members={list}
        onClose={() => setCreating(false)}
        onCreated={() => tickets.reload()}
      />
    </div>
  )
}
