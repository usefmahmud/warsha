import { Link } from 'react-router-dom'
import type { TicketOut } from '../api/types'
import { shortDate } from '../lib/format'
import { Avatar, PriorityChip, TypeChip } from './ui'

interface Props {
  ticket: TicketOut
  projectKey?: string
  draggable?: boolean
  onDragStart?: (ticket: TicketOut) => void
  onDragEnd?: () => void
  onDropOnCard?: (target: TicketOut) => void
  onDragOverCard?: (target: TicketOut, e: React.DragEvent) => void
  dragging?: boolean
}

export function TicketCard({
  ticket,
  projectKey,
  draggable = false,
  onDragStart,
  onDragEnd,
  onDropOnCard,
  onDragOverCard,
  dragging = false,
}: Props) {
  const key = projectKey ? `${projectKey}-${ticket.number}` : ticket.key
  return (
    <div
      draggable={draggable}
      onDragStart={(e) => {
        if (!draggable) return
        e.dataTransfer.effectAllowed = 'move'
        e.dataTransfer.setData('text/plain', ticket.key)
        onDragStart?.(ticket)
      }}
      onDragEnd={onDragEnd}
      onDragOver={(e) => {
        if (!onDragOverCard) return
        e.preventDefault()
        e.stopPropagation()
        onDragOverCard(ticket, e)
      }}
      onDrop={(e) => {
        if (!onDropOnCard) return
        e.preventDefault()
        e.stopPropagation()
        onDropOnCard(ticket)
      }}
      className={`group rounded-xl border border-white/8 bg-ink-800/80 p-3 shadow-sm transition
        hover:border-white/15 hover:bg-ink-700/70 ${dragging ? 'opacity-40' : ''} ${
          draggable ? 'cursor-grab active:cursor-grabbing' : ''
        }`}
    >
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/p/${ticket.project_key ?? projectKey}/t/${key}`}
          className="line-clamp-2 text-[13px] leading-5 font-medium text-slate-100 hover:text-brand-300"
        >
          {ticket.title}
        </Link>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <PriorityChip priority={ticket.priority} />
        <TypeChip type={ticket.type} />
        {(ticket.labels ?? []).slice(0, 2).map((label) => (
          <span
            key={label.id}
            className="chip border-transparent"
            style={{ backgroundColor: `${label.color}22`, color: label.color }}
          >
            {label.name}
          </span>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="font-mono text-[11px] tracking-tight text-slate-500">{key}</span>
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          {(ticket.comment_count ?? 0) > 0 && <span>💬 {ticket.comment_count}</span>}
          {ticket.due_date && <span title="تاريخ الاستحقاق">{shortDate(ticket.due_date)}</span>}
          <Avatar user={ticket.assignee ?? null} size={22} />
        </div>
      </div>
    </div>
  )
}
