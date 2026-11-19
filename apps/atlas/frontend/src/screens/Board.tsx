import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  STATUS_LABEL,
  STATUS_ORDER,
  type BoardColumn,
  type MemberOut,
  type TicketOut,
  type TicketPriority,
  type TicketStatus,
} from '../api/types'
import { errorMessage } from '../auth'
import { NewTicketModal } from '../components/NewTicketModal'
import { TicketCard } from '../components/TicketCard'
import { ErrorBox, Spinner } from '../components/ui'
import { positionBetween } from '../lib/format'
import { useAsync } from '../lib/useAsync'

const PRIORITIES: TicketPriority[] = ['urgent', 'high', 'normal', 'low']

export function BoardScreen() {
  const { projectKey = '' } = useParams()
  const [assignee, setAssignee] = useState('')
  const [priority, setPriority] = useState('')
  const [creating, setCreating] = useState<TicketStatus | null>(null)
  const [dragTicket, setDragTicket] = useState<TicketOut | null>(null)
  const [overColumn, setOverColumn] = useState<TicketStatus | null>(null)
  const [banner, setBanner] = useState<string | null>(null)

  const board = useAsync(
    () => api.board(projectKey, { assignee, priority: priority as TicketPriority | '' }),
    [projectKey, assignee, priority],
  )
  const members = useAsync(() => api.members(projectKey).catch(() => [] as MemberOut[]), [projectKey])

  // Local copy so the drop feels instant; the server response wins on reload.
  const [columns, setColumns] = useState<BoardColumn[] | null>(null)
  useEffect(() => {
    if (!board.data) return
    const byStatus = new Map(board.data.columns.map((c) => [c.status, c.tickets]))
    setColumns(
      STATUS_ORDER.map((status) => ({ status, tickets: byStatus.get(status) ?? [] })),
    )
  }, [board.data])

  const project = board.data?.project
  const list = useMemo(() => members.data ?? [], [members.data])

  function optimisticMove(ticket: TicketOut, status: TicketStatus, beforeKey?: string) {
    if (!columns) return null
    const target = columns.find((c) => c.status === status)
    if (!target) return null
    const rest = target.tickets.filter((t) => t.key !== ticket.key)
    const index = beforeKey ? Math.max(0, rest.findIndex((t) => t.key === beforeKey)) : rest.length
    const prev = index > 0 ? rest[index - 1].position : null
    const next = index < rest.length ? rest[index].position : null
    const position = positionBetween(prev, next)
    const moved: TicketOut = { ...ticket, status, position }
    const nextColumns = columns.map((col) => {
      if (col.status === ticket.status && col.status !== status) {
        return { ...col, tickets: col.tickets.filter((t) => t.key !== ticket.key) }
      }
      if (col.status !== status) return col
      const items = [...rest]
      items.splice(index, 0, moved)
      return { ...col, tickets: items }
    })
    setColumns(nextColumns)
    return position
  }

  async function move(ticket: TicketOut, status: TicketStatus, beforeKey?: string) {
    if (ticket.status === status && !beforeKey) return
    const position = optimisticMove(ticket, status, beforeKey)
    setDragTicket(null)
    setOverColumn(null)
    try {
      await api.transition(ticket.key, status, position ?? undefined)
      board.reload()
    } catch (err) {
      setBanner(errorMessage(err))
      board.reload()
    }
  }

  if (board.loading && !board.data) return <Spinner label="بيحمّل البورد…" />
  if (board.error) return <ErrorBox message={board.error.message} onRetry={board.reload} />

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className="grid size-9 place-items-center rounded-xl text-xs font-black text-white"
            style={{ backgroundColor: project?.color ?? '#4f46e5' }}
          >
            {projectKey.slice(0, 2)}
          </span>
          <div>
            <h1 className="text-base leading-tight font-bold text-slate-100">{project?.name ?? projectKey}</h1>
            <div className="mt-1 flex items-center gap-1 text-[11px]">
              <Link to={`/p/${projectKey}/board`} className="rounded-md bg-white/8 px-2 py-0.5 text-slate-200">
                بورد
              </Link>
              <Link to={`/p/${projectKey}/list`} className="rounded-md px-2 py-0.5 text-slate-400 hover:bg-white/6">
                ليستة
              </Link>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select className="input !w-auto !py-1.5 text-xs" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">كل المسؤولين</option>
            {list.map((m) => (
              <option key={m.user.id} value={m.user.username}>
                {m.user.full_name || m.user.username}
              </option>
            ))}
          </select>
          <select className="input !w-auto !py-1.5 text-xs" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">كل الأولويات</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <button type="button" className="btn-primary !py-1.5" onClick={() => setCreating('todo')}>
            + تذكرة
          </button>
        </div>
      </header>

      {banner && (
        <div className="rounded-xl border border-amber-400/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          <span>{banner}</span>
          <button type="button" className="ms-3 underline" onClick={() => setBanner(null)}>
            تمام
          </button>
        </div>
      )}

      <div className="flex gap-3 overflow-x-auto pb-2">
        {(columns ?? []).map((column) => (
          <section
            key={column.status}
            onDragOver={(e) => {
              e.preventDefault()
              setOverColumn(column.status)
            }}
            onDragLeave={() => setOverColumn((prev) => (prev === column.status ? null : prev))}
            onDrop={(e) => {
              e.preventDefault()
              if (dragTicket) void move(dragTicket, column.status)
            }}
            className={`flex w-72 shrink-0 flex-col rounded-2xl border bg-ink-850/60 p-2 transition ${
              overColumn === column.status ? 'border-brand-400/50 bg-brand-500/5' : 'border-white/8'
            }`}
          >
            <div className="mb-2 flex items-center justify-between px-1">
              <h2 className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                {STATUS_LABEL[column.status]}
                <span className="rounded-md bg-white/8 px-1.5 text-[11px] text-slate-400">
                  {column.tickets.length}
                </span>
              </h2>
              <button
                type="button"
                className="rounded-md px-1.5 text-slate-500 hover:bg-white/8 hover:text-slate-200"
                onClick={() => setCreating(column.status)}
                aria-label={`إضافة تذكرة في ${STATUS_LABEL[column.status]}`}
              >
                +
              </button>
            </div>

            <div className="flex min-h-24 flex-1 flex-col gap-2">
              {column.tickets.map((ticket) => (
                <TicketCard
                  key={ticket.key}
                  ticket={ticket}
                  projectKey={projectKey}
                  draggable
                  dragging={dragTicket?.key === ticket.key}
                  onDragStart={setDragTicket}
                  onDragEnd={() => {
                    setDragTicket(null)
                    setOverColumn(null)
                  }}
                  onDropOnCard={(target) => {
                    if (dragTicket && dragTicket.key !== target.key) {
                      void move(dragTicket, target.status, target.key)
                    }
                  }}
                />
              ))}
              {column.tickets.length === 0 && (
                <p className="rounded-xl border border-dashed border-white/8 py-6 text-center text-[11px] text-slate-600">
                  اسحب تذكرة هنا
                </p>
              )}
            </div>
          </section>
        ))}
      </div>

      <NewTicketModal
        open={creating !== null}
        projectKey={projectKey}
        members={list}
        defaultStatus={creating ?? 'todo'}
        onClose={() => setCreating(null)}
        onCreated={() => board.reload()}
      />
    </div>
  )
}
