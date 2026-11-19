import type {
  ActivityOut,
  BoardOut,
  CommentOut,
  LabelOut,
  MemberOut,
  MyWorkOut,
  NotificationOut,
  Page,
  ProjectDetail,
  ProjectOut,
  TicketCreateInput,
  TicketOut,
  TicketPriority,
  TicketStatus,
  TicketType,
  TokenOut,
  UserOut,
} from './types'
import {
  normActivity,
  normBoard,
  normComment,
  normLabel,
  normMember,
  normMyWork,
  normNotification,
  normPage,
  normProject,
  normTicket,
  normUser,
} from './normalize'

/**
 * Same-origin API client. The bearer token lives in localStorage and is sent on
 * every call except login. Errors are normalised into `ApiError` so screens can
 * show the backend's own code/message (`{"error":{"code","message",...}}`).
 */
const TOKEN_KEY = 'atlas.token'
const BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/+$/, '')

export class ApiError extends Error {
  status: number
  code: string
  details: unknown
  requestId: string | null

  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details ?? null
    this.requestId = requestId ?? null
  }
}

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string): void {
    localStorage.setItem(TOKEN_KEY, token)
  },
  clear(): void {
    localStorage.removeItem(TOKEN_KEY)
  },
}

type Json = Record<string, unknown>

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  auth?: boolean
}

function parseJson(text: string): Json | null {
  try {
    return JSON.parse(text) as Json
  } catch {
    return null
  }
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = tokenStore.get()
  if (opts.auth !== false && token) headers.Authorization = `Bearer ${token}`
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      method: opts.method ?? 'GET',
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'مش قادر أوصل للسيرفر — اتأكد إن الـAPI شغّال')
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  const data = text ? parseJson(text) : null
  const envelope = (data?.error ?? null) as
    | { code?: string; message?: string; details?: unknown; request_id?: string | null }
    | null

  if (!res.ok) {
    if (res.status === 401 && opts.auth !== false) {
      tokenStore.clear()
      window.dispatchEvent(new Event('atlas:unauthorised'))
    }
    const fallback = typeof data?.detail === 'string' ? (data.detail as string) : 'حصل خطأ غير متوقع'
    throw new ApiError(
      res.status,
      envelope?.code ?? `HTTP_${res.status}`,
      envelope?.message ?? fallback,
      envelope?.details,
      envelope?.request_id,
    )
  }

  return (data ?? {}) as T
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const out = search.toString()
  return out ? `?${out}` : ''
}

export interface TicketFilters {
  status?: TicketStatus | ''
  priority?: TicketPriority | ''
  type?: TicketType | ''
  assignee?: string
  label?: string
  q?: string
  mine?: boolean
  limit?: number
  offset?: number
  sort?: string
  order?: 'asc' | 'desc'
}

async function getPage<T>(path: string, map: (raw: unknown) => T): Promise<Page<T>> {
  return normPage(await request<unknown>(path), map)
}

export const api = {
  // --- auth ---
  async login(email: string, password: string): Promise<TokenOut> {
    const raw = await request<Json>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    })
    return {
      access_token: String(raw.access_token ?? ''),
      token_type: String(raw.token_type ?? 'bearer'),
      expires_in: Number(raw.expires_in ?? 0),
      user: normUser(raw.user) as UserOut,
    }
  },
  async register(input: { email: string; name: string; username: string; password: string }): Promise<TokenOut> {
    const raw = await request<Json>('/auth/register', { method: 'POST', body: input, auth: false })
    return {
      access_token: String(raw.access_token ?? ''),
      token_type: String(raw.token_type ?? 'bearer'),
      expires_in: Number(raw.expires_in ?? 0),
      user: normUser(raw.user) as UserOut,
    }
  },
  async me(): Promise<UserOut> {
    return normUser(await request<unknown>('/auth/me')) as UserOut
  },

  // --- projects ---
  projects(): Promise<Page<ProjectOut>> {
    return getPage(`/projects${qs({ limit: 200 })}`, normProject)
  },
  async project(ref: string): Promise<ProjectDetail> {
    const raw = (await request<Json>(`/projects/${encodeURIComponent(ref)}`)) as Json
    return {
      ...normProject(raw),
      members: Array.isArray(raw.members) ? raw.members.map(normMember) : undefined,
      labels: Array.isArray(raw.labels) ? raw.labels.map(normLabel) : undefined,
    }
  },
  async members(ref: string): Promise<MemberOut[]> {
    const raw = await request<unknown>(`/projects/${encodeURIComponent(ref)}/members`)
    return Array.isArray(raw) ? raw.map(normMember) : normPage(raw, normMember).items
  },
  async labels(ref: string): Promise<LabelOut[]> {
    const raw = await request<unknown>(`/projects/${encodeURIComponent(ref)}/labels`)
    return Array.isArray(raw) ? raw.map(normLabel) : normPage(raw, normLabel).items
  },
  async createProject(input: { key: string; name: string; description?: string; color?: string }): Promise<ProjectOut> {
    return normProject(await request<unknown>('/projects', { method: 'POST', body: input }))
  },

  // --- board / tickets ---
  async board(ref: string, filters: TicketFilters = {}): Promise<BoardOut> {
    const { status, priority, assignee, label } = filters
    const raw = await request<unknown>(
      `/projects/${encodeURIComponent(ref)}/board${qs({ status, priority, assignee, label })}`,
    )
    return normBoard(raw)
  },
  projectTickets(ref: string, filters: TicketFilters = {}): Promise<Page<TicketOut>> {
    return getPage(`/projects/${encodeURIComponent(ref)}/tickets${qs(filters as never)}`, normTicket)
  },
  tickets(filters: TicketFilters = {}): Promise<Page<TicketOut>> {
    return getPage(`/tickets${qs(filters as never)}`, normTicket)
  },
  async ticket(ref: string): Promise<TicketOut> {
    return normTicket(await request<unknown>(`/tickets/${encodeURIComponent(ref)}`))
  },
  async createTicket(input: TicketCreateInput): Promise<TicketOut> {
    const body = {
      ...input,
      // both revisions: A reads `description`/`position`, B reads `description_md`/`board_position`
      description_md: input.description,
    }
    return normTicket(await request<unknown>('/tickets', { method: 'POST', body }))
  },
  async updateTicket(ref: string, patch: Record<string, unknown>): Promise<TicketOut> {
    const body: Record<string, unknown> = { ...patch }
    if ('description' in body) body.description_md = body.description
    if ('position' in body) body.board_position = body.position
    return normTicket(await request<unknown>(`/tickets/${encodeURIComponent(ref)}`, { method: 'PATCH', body }))
  },
  async transition(ref: string, status: TicketStatus, position?: number): Promise<TicketOut> {
    const body: Record<string, unknown> = { status, to: status }
    if (position !== undefined) {
      body.position = position
      body.board_position = position
    }
    const raw = (await request<Json>(`/tickets/${encodeURIComponent(ref)}/transition`, { method: 'POST', body })) as Json
    return normTicket(raw.ticket ?? raw)
  },

  // --- comments / activity ---
  comments(ref: string, limit = 100): Promise<Page<CommentOut>> {
    return getPage(`/tickets/${encodeURIComponent(ref)}/comments${qs({ limit })}`, normComment)
  },
  async addComment(ref: string, body: string): Promise<CommentOut> {
    const raw = await request<unknown>(`/tickets/${encodeURIComponent(ref)}/comments`, {
      method: 'POST',
      body: { body, body_md: body },
    })
    return normComment(raw)
  },
  activity(ref: string, limit = 100): Promise<Page<ActivityOut>> {
    return getPage(`/tickets/${encodeURIComponent(ref)}/activity${qs({ limit })}`, normActivity)
  },

  // --- personal ---
  async myWork(): Promise<MyWorkOut> {
    return normMyWork(await request<unknown>('/me/work'))
  },
  notifications(limit = 50): Promise<Page<NotificationOut>> {
    return getPage(`/notifications${qs({ limit })}`, normNotification)
  },
  /** The route name differs between backend revisions (`/unread-count` vs `/unread_count`). */
  async unreadCount(): Promise<number> {
    for (const path of ['/notifications/unread_count', '/notifications/unread-count']) {
      try {
        const out = await request<{ unread?: number; count?: number }>(path)
        return out.unread ?? out.count ?? 0
      } catch (err) {
        if ((err as ApiError)?.status === 404) continue
        throw err
      }
    }
    return 0
  },
  async markRead(id: number | string): Promise<NotificationOut> {
    return normNotification(await request<unknown>(`/notifications/${id}/read`, { method: 'POST' }))
  },
  markAllRead(): Promise<unknown> {
    return request<unknown>('/notifications/read-all', { method: 'POST' })
  },
}
