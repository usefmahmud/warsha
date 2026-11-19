import type { Filter, Todo, TodoCreate, TodoList, TodoPatch } from './types'

const BASE = '/api'

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'مش قادر أوصل للسيرفر — اتأكد إن الـbackend شغال')
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  const body = text ? safeJson(text) : null

  if (!res.ok) {
    const err = (body as { error?: { code?: string; message?: string; details?: unknown } })?.error
    throw new ApiError(
      res.status,
      err?.code ?? 'ERROR',
      err?.message ?? `فشل الطلب (${res.status})`,
      err?.details,
    )
  }

  return body as T
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export function listTodos(filter: Filter, q: string): Promise<TodoList> {
  const params = new URLSearchParams()
  if (filter === 'open') params.set('done', 'false')
  if (filter === 'done') params.set('done', 'true')
  const needle = q.trim()
  if (needle) params.set('q', needle)
  const qs = params.toString()
  return request<TodoList>(`/todos${qs ? `?${qs}` : ''}`)
}

export function createTodo(payload: TodoCreate): Promise<Todo> {
  return request<Todo>('/todos', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateTodo(id: string, payload: TodoPatch): Promise<Todo> {
  return request<Todo>(`/todos/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function deleteTodo(id: string): Promise<void> {
  return request<void>(`/todos/${id}`, { method: 'DELETE' })
}

export function toggleTodo(id: string): Promise<Todo> {
  return request<Todo>(`/todos/${id}/toggle`, { method: 'POST' })
}
