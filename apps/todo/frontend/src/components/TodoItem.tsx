import { useState } from 'react'

import { PRIORITY_META, formatDue } from '../lib/format'
import type { Todo } from '../types'

interface Props {
  todo: Todo
  onToggle: (id: string) => void
  onDelete: (id: string) => void
  onSave: (id: string, title: string, notes: string, priority: Todo['priority']) => void
  onEditStart: (id: string) => void
  onEditCancel: () => void
  editing: boolean
  busy: boolean
}

export default function TodoItem({
  todo,
  onToggle,
  onDelete,
  onSave,
  onEditStart,
  onEditCancel,
  editing,
  busy,
}: Props) {
  const meta = PRIORITY_META[todo.priority]
  const due = formatDue(todo.due_date)

  return (
    <li
      className={`group animate-rise rounded-2xl border p-3 transition ${
        todo.done
          ? 'border-white/5 bg-white/[0.02]'
          : 'border-white/10 bg-white/[0.045] hover:border-white/20 hover:bg-white/[0.07]'
      } ${busy ? 'opacity-60' : ''}`}
    >
      {editing ? (
        <EditForm
          todo={todo}
          onSave={(title, notes, priority) => onSave(todo.id, title, notes, priority)}
          onCancel={onEditCancel}
        />
      ) : (
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => onToggle(todo.id)}
            disabled={busy}
            aria-pressed={todo.done}
            aria-label={todo.done ? 'رجّعها غير منجزة' : 'علّمها منجزة'}
            className={`mt-0.5 grid size-6 shrink-0 cursor-pointer place-items-center rounded-lg border transition ${
              todo.done
                ? 'border-emerald-400/60 bg-emerald-500/25 text-emerald-300'
                : 'border-white/25 bg-transparent text-transparent hover:border-brand-400 hover:bg-brand-500/10 hover:text-brand-300/50'
            }`}
          >
            <svg viewBox="0 0 20 20" fill="none" className="size-3.5" aria-hidden="true">
              <path
                d="M4 10.5 8 14.5 16 6"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`min-w-0 break-words text-[15px] leading-6 ${
                  todo.done ? 'text-slate-500 line-through' : 'text-slate-100'
                }`}
              >
                {todo.title}
              </span>
              {todo.priority !== 'normal' && (
                <span className={`chip ${meta.chip}`}>{meta.label}</span>
              )}
              {due && (
                <span
                  className={`chip ${
                    due.overdue && !todo.done
                      ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                      : 'border-white/10 bg-white/5 text-slate-400'
                  }`}
                >
                  {due.label}
                </span>
              )}
            </div>
            {todo.notes && (
              <p
                className={`mt-1 text-[13px] leading-5 whitespace-pre-line ${
                  todo.done ? 'text-slate-600' : 'text-slate-400'
                }`}
              >
                {todo.notes}
              </p>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-1 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100 max-md:opacity-100">
            <button
              type="button"
              onClick={() => onEditStart(todo.id)}
              disabled={busy}
              className="btn btn-ghost !px-2 !py-1.5 text-xs"
              title="تعديل"
            >
              تعديل
            </button>
            <button
              type="button"
              onClick={() => onDelete(todo.id)}
              disabled={busy}
              className="btn btn-danger !px-2 !py-1.5 text-xs"
              title="حذف"
            >
              حذف
            </button>
          </div>
        </div>
      )}
    </li>
  )
}

function EditForm({
  todo,
  onSave,
  onCancel,
}: {
  todo: Todo
  onSave: (title: string, notes: string, priority: Todo['priority']) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState(todo.title)
  const [notes, setNotes] = useState(todo.notes ?? '')
  const [priority, setPriority] = useState<Todo['priority']>(todo.priority)

  const tooLong = title.trim().length > 200
  const canSave = title.trim().length > 0 && !tooLong

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (canSave) onSave(title.trim(), notes.trim(), priority)
      }}
    >
      <input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onCancel()
        }}
        className="field"
        maxLength={400}
        aria-label="عنوان المهمة"
      />
      {tooLong && <p className="text-xs text-rose-400">العنوان أقصى حاجة 200 حرف</p>}
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        rows={2}
        placeholder="ملاحظات (اختياري)"
        className="field resize-y"
        onKeyDown={(e) => {
          if (e.key === 'Escape') onCancel()
        }}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1.5">
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
            >
              {PRIORITY_META[p].label}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5">
          <button type="button" onClick={onCancel} className="btn btn-ghost !px-3 !py-1.5 text-xs">
            إلغاء
          </button>
          <button
            type="submit"
            disabled={!canSave}
            className="btn btn-primary !px-3 !py-1.5 text-xs"
          >
            حفظ
          </button>
        </div>
      </div>
    </form>
  )
}
