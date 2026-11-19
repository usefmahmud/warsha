import type {
  ActivityOut,
  BoardOut,
  CommentOut,
  LabelOut,
  MemberOut,
  MyWorkOut,
  NotificationOut,
  Page,
  ProjectOut,
  TicketOut,
  UserBrief,
} from './types'

/**
 * The backend exists in two shapes:
 *   A) `full_name` / `description` / `position` / `member_count` / `is_archived`
 *   B) `name` / `description_md` / `board_position` / `members_count` / `archived_at`
 * Screens only ever see shape A. These adapters accept either, so the same build
 * works against both revisions while the API settles.
 */
type Raw = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any

const ANON: UserBrief = { id: 0, username: '', full_name: '', avatar_url: null, color: '#64748b' }

export function normUser(raw: unknown): UserBrief | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Raw
  return {
    id: r.id ?? 0,
    username: r.username ?? '',
    full_name: r.full_name ?? r.name ?? r.username ?? '',
    avatar_url: r.avatar_url ?? null,
    color: r.color ?? '#64748b',
  }
}

export function normProject(raw: unknown): ProjectOut {
  const r = (raw ?? {}) as Raw
  return {
    id: r.id,
    key: r.key ?? '',
    name: r.name ?? '',
    description: r.description ?? '',
    color: r.color ?? '#4f46e5',
    owner: normUser(r.owner) ?? undefined,
    is_archived: r.is_archived ?? Boolean(r.archived_at),
    ticket_count: r.ticket_count ?? 0,
    member_count: r.member_count ?? r.members_count ?? 0,
    created_at: r.created_at ?? '',
    updated_at: r.updated_at ?? r.created_at ?? '',
  }
}

export function normLabel(raw: unknown): LabelOut {
  const r = (raw ?? {}) as Raw
  return { id: r.id, name: r.name ?? '', color: r.color ?? '#94a3b8', project_id: r.project_id ?? '' }
}

export function normTicket(raw: unknown): TicketOut {
  const r = (raw ?? {}) as Raw
  return {
    id: r.id,
    key: r.key ?? '',
    project_id: r.project_id ?? '',
    project_key: r.project_key ?? String(r.key ?? '').split('-')[0],
    number: r.number ?? 0,
    title: r.title ?? '',
    description: r.description ?? r.description_md ?? '',
    type: r.type ?? 'task',
    priority: r.priority ?? 'normal',
    status: r.status ?? 'backlog',
    assignee: normUser(r.assignee),
    reporter: normUser(r.reporter),
    parent_id: r.parent_id ?? null,
    parent_key: r.parent_key ?? null,
    due_date: r.due_date ?? null,
    points: r.points ?? r.estimate_points ?? null,
    position: r.position ?? r.board_position ?? 0,
    attachments: r.attachments ?? [],
    labels: Array.isArray(r.labels) ? r.labels.map(normLabel) : [],
    comment_count: r.comment_count ?? 0,
    subtask_count: r.subtask_count ?? r.children_count ?? 0,
    created_at: r.created_at ?? '',
    updated_at: r.updated_at ?? r.created_at ?? '',
    closed_at: r.closed_at ?? null,
  }
}

export function normPage<T>(raw: unknown, map: (item: unknown) => T): Page<T> {
  const r = (raw ?? {}) as Raw
  const items = Array.isArray(r.items) ? r.items.map(map) : []
  const total = typeof r.total === 'number' ? r.total : items.length
  const limit = typeof r.limit === 'number' ? r.limit : items.length
  const offset = typeof r.offset === 'number' ? r.offset : 0
  return { items, total, limit, offset, has_more: r.has_more ?? offset + items.length < total }
}

export function normBoard(raw: unknown): BoardOut {
  const r = (raw ?? {}) as Raw
  const columns = Array.isArray(r.columns) ? r.columns : []
  return {
    project: normProject(r.project),
    columns: columns.map((col: Raw) => ({
      status: col.status,
      tickets: (Array.isArray(col.tickets) ? col.tickets : Array.isArray(col.items) ? col.items : []).map(normTicket),
    })),
  }
}

export function normComment(raw: unknown): CommentOut {
  const r = (raw ?? {}) as Raw
  return {
    id: r.id,
    ticket_id: r.ticket_id ?? '',
    ticket_key: r.ticket_key ?? '',
    author: normUser(r.author) ?? ANON,
    body: r.body ?? r.body_md ?? '',
    edited: r.edited ?? Boolean(r.edited_at),
    mentions: r.mentions ?? [],
    created_at: r.created_at ?? '',
    updated_at: r.updated_at ?? r.edited_at ?? r.created_at ?? '',
  }
}

export function normActivity(raw: unknown): ActivityOut {
  const r = (raw ?? {}) as Raw
  return {
    id: r.id,
    project_id: r.project_id ?? '',
    ticket_id: r.ticket_id ?? null,
    ticket_key: r.ticket_key ?? null,
    actor: normUser(r.actor),
    action: r.action ?? '',
    field: r.field ?? null,
    old_value: r.old_value ?? null,
    new_value: r.new_value ?? null,
    created_at: r.created_at ?? '',
  }
}

export function normNotification(raw: unknown): NotificationOut {
  const r = (raw ?? {}) as Raw
  const payload = (r.payload ?? {}) as Raw
  const kind = r.type ?? 'mention'
  return {
    id: r.id ?? r.notification_id ?? '',
    type: kind,
    message: r.message ?? r.text ?? payload.snippet ?? payload.message ?? `${kind} · ${r.ticket_key ?? ''}`,
    is_read: r.is_read ?? Boolean(r.read_at),
    actor: normUser(r.actor),
    ticket_id: r.ticket_id ?? payload.ticket_id ?? null,
    ticket_key: r.ticket_key ?? payload.ticket_key ?? null,
    created_at: r.created_at ?? '',
  }
}

export function normMember(raw: unknown): MemberOut {
  const r = (raw ?? {}) as Raw
  return {
    user: normUser(r.user) ?? ANON,
    role: r.role ?? r.role_in_project ?? 'member',
    joined_at: r.joined_at ?? r.added_at ?? '',
  }
}

export function normMyWork(raw: unknown): MyWorkOut {
  const r = (raw ?? {}) as Raw
  const assigned = Array.isArray(r.assigned) ? r.assigned.map(normTicket) : []
  const mentionsRaw: unknown[] = Array.isArray(r.mentions) ? r.mentions : []
  const mentions = mentionsRaw.map((item) => {
    const row = (item ?? {}) as Raw
    // revision B nests the ticket: {notification_id, ticket: {...}}
    if (row.notification_id && row.ticket) {
      return normNotification({
        ...row,
        id: row.notification_id,
        message: row.snippet,
        is_read: row.unread === undefined ? undefined : !row.unread,
        ticket_key: (row.ticket as Raw).key,
        ticket_id: (row.ticket as Raw).id,
      })
    }
    return normNotification(safeNotification(row))
  })
  return { assigned, mentions }
}

function safeNotification(row: Raw): Raw {
  if (row.id || row.notification_id || row.message || row.text || row.payload) return row
  return { ...row, payload: { snippet: row.snippet } }
}
