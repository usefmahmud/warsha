import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { ApiError, createTodo, deleteTodo, listTodos, toggleTodo, updateTodo } from './api'
import TodoItem from './components/TodoItem'
import { PRIORITY_META, plural } from './lib/format'
import type { Filter, Priority, Todo, TodoList } from './types'

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'الكل' },
  { value: 'open', label: 'مفتوح' },
  { value: 'done', label: 'منجز' },
]

const EMPTY: TodoList = { items: [], count: 0, open_count: 0, done_count: 0 }

export default function App() {
  const [board, setBoard] = useState<TodoList>(EMPTY)
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  // form state
  const [title, setTitle] = useState('')
  const [notes, setNotes] = useState('')
  const [priority, setPriority] = useState<Priority>('normal')
  const [dueDate, setDueDate] = useState('')
  const [showDetails, setShowDetails] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const inputRef = useRef<HTMLInputElement>(null)
  const toastTimer = useRef<number | null>(null)

  const notify = useCallback((msg: string) => {
    setToast(msg)
    if (toastTimer.current) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 2200)
  }, [])

  const fail = useCallback((e: unknown) => {
    setError(e instanceof ApiError ? e.message : 'حصل خطأ غير متوقع')
  }, [])

  // debounce the search box so typing doesn't hammer the API
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(query), 250)
    return () => window.clearTimeout(t)
  }, [query])

  const load = useCallback(
    async (f: Filter, q: string, silent = false) => {
      if (!silent) setLoading(true)
      try {
        const data = await listTodos(f, q)
        setBoard(data)
        setError(null)
      } catch (e) {
        fail(e)
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [fail],
  )

  useEffect(() => {
    void load(filter, debounced)
  }, [filter, debounced, load])

  const refresh = useCallback(
    () => load(filter, debounced, true),
    [filter, debounced, load],
  )

  const visible = useMemo(() => {
    // The API already filters + sorts; this is a safety net for optimistic edits.
    const needle = debounced.trim().toLowerCase()
    if (!needle) return board.items
    return board.items.filter(
      (t) =>
        t.title.toLowerCase().includes(needle) ||
        (t.notes ?? '').toLowerCase().includes(needle),
    )
  }, [board.items, debounced])

  async function onAdd(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) {
      setError('اكتب عنوان للمهمة الأول')
      inputRef.current?.focus()
      return
    }
    if (trimmed.length > 200) {
      setError('العنوان أقصى حاجة 200 حرف')
      return
    }
    setSubmitting(true)
    try {
      await createTodo({
        title: trimmed,
        notes: notes.trim() ? notes.trim() : null,
        priority,
        due_date: dueDate || null,
      })
      setTitle('')
      setNotes('')
      setDueDate('')
      setPriority('normal')
      setShowDetails(false)
      setError(null)
      await refresh()
      notify('اتضافت ✓')
      inputRef.current?.focus()
    } catch (err) {
      fail(err)
    } finally {
      setSubmitting(false)
    }
  }

  async function onToggle(id: string) {
    setBusyId(id)
    setBoard((b) => ({
      ...b,
      items: b.items.map((t) => (t.id === id ? { ...t, done: !t.done } : t)),
    }))
    try {
      await toggleTodo(id)
      await refresh()
    } catch (err) {
      fail(err)
      await refresh()
    } finally {
      setBusyId(null)
    }
  }

  async function onDelete(id: string) {
    const target = board.items.find((t) => t.id === id)
    if (!window.confirm(`تحذف «${target?.title ?? 'المهمة'}»؟`)) return
    setBusyId(id)
    try {
      await deleteTodo(id)
      setBoard((b) => ({ ...b, items: b.items.filter((t) => t.id !== id) }))
      await refresh()
      notify('اتحذفت')
    } catch (err) {
      fail(err)
    } finally {
      setBusyId(null)
    }
  }

  async function onSave(
    id: string,
    nextTitle: string,
    nextNotes: string,
    nextPriority: Priority,
  ) {
    setBusyId(id)
    try {
      const updated = await updateTodo(id, {
        title: nextTitle,
        notes: nextNotes ? nextNotes : null,
        priority: nextPriority,
      })
      setBoard((b) => ({
        ...b,
        items: b.items.map((t) => (t.id === id ? updated : t)),
      }))
      setEditingId(null)
      notify('اتحفظت ✓')
      await refresh()
    } catch (err) {
      fail(err)
    } finally {
      setBusyId(null)
    }
  }

  const total = board.open_count + board.done_count
  const progress = total > 0 ? Math.round((board.done_count / total) * 100) : 0

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-12">
      {/* header */}
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2.5">
            <span className="grid size-10 place-items-center rounded-xl bg-brand-600/90 text-white shadow-lg shadow-brand-600/25">
              <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden="true">
                <path
                  d="M4 7.5 7 10.5 12 5M4 16.5 7 19.5 12 14M14 7.5h6M14 16.5h6"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">قائمة المهام</h1>
              <p className="text-xs text-slate-400">
                {total === 0
                  ? 'ابدأ بإضافة أول مهمة'
                  : `${plural(board.open_count)} مفتوحة · ${board.done_count} منجزة`}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-end">
            <div className="text-2xl font-bold tabular-nums text-white">{progress}%</div>
            <div className="text-[11px] text-slate-500">خلصت</div>
          </div>
          <div className="h-11 w-2.5 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
            <div
              className="h-full w-full rounded-full bg-gradient-to-t from-brand-600 to-emerald-400 transition-[height] duration-500"
              style={{ height: `${progress}%`, transformOrigin: 'bottom', marginTop: `${100 - progress}%` }}
            />
          </div>
        </div>
      </header>

      {/* add form */}
      <form onSubmit={onAdd} className="card mb-5 p-3 sm:p-4">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="إيه اللي محتاج تعمله؟"
            maxLength={400}
            className="field !py-3 text-[15px]"
            aria-label="عنوان المهمة الجديدة"
          />
          <button
            type="submit"
            disabled={submitting}
            className="btn btn-primary shrink-0 !px-5 !py-3"
          >
            {submitting ? '...' : 'إضافة'}
          </button>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowDetails((v) => !v)}
            className="btn btn-ghost !px-2.5 !py-1 text-xs"
            aria-expanded={showDetails}
          >
            {showDetails ? 'إخفاء التفاصيل' : '+ تفاصيل'}
          </button>
          {(['low', 'normal', 'high'] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPriority(p)}
              className={`btn !px-2.5 !py-1 text-xs ${
                priority === p
                  ? `border ${PRIORITY_META[p].chip}`
                  : 'border border-white/10 text-slate-400 hover:bg-white/5'
              }`}
              aria-pressed={priority === p}
            >
              {PRIORITY_META[p].label}
            </button>
          ))}
          <span className="ms-auto text-[11px] tabular-nums text-slate-500">
            {title.trim().length}/200
          </span>
        </div>

        {showDetails && (
          <div className="animate-rise mt-3 grid gap-2 sm:grid-cols-[1fr_auto]">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="ملاحظات (اختياري)"
              className="field resize-y"
              aria-label="ملاحظات"
            />
            <label className="flex flex-col gap-1 text-[11px] text-slate-400">
              تاريخ التسليم
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="field !py-2"
              />
            </label>
          </div>
        )}
      </form>

      {/* filters + search */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-xl border border-white/10 bg-white/5 p-1">
          {FILTERS.map((f) => {
            const count =
              f.value === 'all' ? total : f.value === 'open' ? board.open_count : board.done_count
            const active = filter === f.value
            return (
              <button
                key={f.value}
                type="button"
                onClick={() => setFilter(f.value)}
                className={`cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  active ? 'bg-brand-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
                aria-pressed={active}
              >
                {f.label}
                <span
                  className={`ms-1.5 tabular-nums ${active ? 'text-white/75' : 'text-slate-500'}`}
                >
                  {count}
                </span>
              </button>
            )
          })}
        </div>

        <div className="relative min-w-[160px] flex-1">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="ابحث…"
            className="field !py-2 ps-9"
            aria-label="بحث"
          />
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-slate-500"
            aria-hidden="true"
          >
            <circle cx="9" cy="9" r="5.5" stroke="currentColor" strokeWidth="1.7" />
            <path d="m13.5 13.5 3 3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
        </div>
      </div>

      {/* error banner */}
      {error && (
        <div className="animate-rise mb-4 flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          <span className="flex-1">{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="cursor-pointer text-rose-300/70 hover:text-rose-200"
            aria-label="إغلاق"
          >
            ✕
          </button>
        </div>
      )}

      {/* list */}
      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-2xl border border-white/5 bg-white/[0.03]" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          filtered={Boolean(debounced.trim()) || filter !== 'all'}
          onReset={() => {
            setQuery('')
            setFilter('all')
          }}
        />
      ) : (
        <ul className="space-y-2">
          {visible.map((todo: Todo) => (
            <TodoItem
              key={todo.id}
              todo={todo}
              editing={editingId === todo.id}
              busy={busyId === todo.id}
              onToggle={onToggle}
              onDelete={onDelete}
              onSave={onSave}
              onEditStart={(id) => {
                setEditingId(id)
                setError(null)
              }}
              onEditCancel={() => setEditingId(null)}
            />
          ))}
        </ul>
      )}

      <footer className="mt-10 flex items-center justify-between text-[11px] text-slate-600">
        <span>TODO · FastAPI + React</span>
        <span className="tabular-nums">
          {board.done_count}/{total} منجز
        </span>
      </footer>

      {/* toast */}
      {toast && (
        <div
          className="animate-rise fixed bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-sm text-emerald-200 shadow-lg backdrop-blur"
          role="status"
        >
          {toast}
        </div>
      )}
    </div>
  )
}

function EmptyState({ filtered, onReset }: { filtered: boolean; onReset: () => void }) {
  return (
    <div className="card animate-rise grid place-items-center px-6 py-14 text-center">
      <div className="mb-3 grid size-14 place-items-center rounded-2xl border border-white/10 bg-white/5 text-slate-500">
        <svg viewBox="0 0 24 24" fill="none" className="size-7" aria-hidden="true">
          <path
            d="M5 5.5 9 9.5l10-10M5 15.5l4 4 10-10"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <p className="text-sm text-slate-300">
        {filtered ? 'مفيش نتايج مطابقة' : 'مفيش مهام لسه'}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        {filtered ? 'جرّب فلتر أو بحث تاني' : 'اكتب مهمة فوق واضغط «إضافة»'}
      </p>
      {filtered && (
        <button type="button" onClick={onReset} className="btn btn-ghost mt-4 text-xs">
          صفّي الفلاتر
        </button>
      )}
    </div>
  )
}
