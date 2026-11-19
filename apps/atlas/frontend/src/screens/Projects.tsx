import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { errorMessage } from '../auth'
import { EmptyState, ErrorBox, Field, Modal, Spinner } from '../components/ui'
import { useAsync } from '../lib/useAsync'
import { shortDate } from '../lib/format'

const PALETTE = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6']

export function ProjectsScreen() {
  const projects = useAsync(() => api.projects(), [])
  const [creating, setCreating] = useState(false)
  const [key, setKey] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(PALETTE[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create(e: React.FormEvent) {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await api.createProject({ key, name, description, color })
      setCreating(false)
      setKey('')
      setName('')
      setDescription('')
      projects.reload()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const items = projects.data?.items ?? []

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-100">المشاريع</h1>
          <p className="mt-0.5 text-xs text-slate-400">
            {projects.data ? `${projects.data.total} مشروع` : 'بيحمّل…'}
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
          + مشروع جديد
        </button>
      </header>

      {projects.loading && !projects.data && <Spinner />}
      {projects.error && <ErrorBox message={projects.error.message} onRetry={projects.reload} />}

      {!projects.loading && !projects.error && items.length === 0 && (
        <EmptyState
          icon="🗂️"
          title="مفيش مشاريع لسه"
          hint="ابدأ بأول مشروع، وبعدها ضيف تذاكر على البورد."
          action={
            <button type="button" className="btn-primary mt-2" onClick={() => setCreating(true)}>
              إنشاء مشروع
            </button>
          }
        />
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((p) => (
          <Link
            key={p.id}
            to={`/p/${p.key}/board`}
            className="card group p-4 transition hover:border-white/15 hover:bg-white/6"
          >
            <div className="flex items-start gap-3">
              <span
                className="grid size-10 shrink-0 place-items-center rounded-xl text-sm font-black text-white"
                style={{ backgroundColor: p.color }}
              >
                {p.key.slice(0, 2)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-100 group-hover:text-brand-200">
                  {p.name}
                </p>
                <p className="truncate font-mono text-[11px] text-slate-500">{p.key}</p>
              </div>
              {p.is_archived && (
                <span className="chip border-slate-400/20 bg-slate-500/15 text-slate-300">مؤرشف</span>
              )}
            </div>

            {p.description && (
              <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-400">{p.description}</p>
            )}

            <div className="mt-4 flex items-center gap-3 text-[11px] text-slate-400">
              <span>🎫 {p.ticket_count} تذكرة</span>
              <span>👥 {p.member_count}</span>
              <span className="ms-auto text-slate-500">{shortDate(p.updated_at)}</span>
            </div>
          </Link>
        ))}
      </div>

      <Modal
        open={creating}
        title="مشروع جديد"
        onClose={() => setCreating(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setCreating(false)}>
              إلغاء
            </button>
            <button type="submit" form="new-project" className="btn-primary" disabled={busy}>
              {busy ? 'بيعمل…' : 'إنشاء'}
            </button>
          </>
        }
      >
        <form id="new-project" onSubmit={create} className="space-y-3">
          <Field label="اسم المشروع">
            <input className="input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Atlas Platform" />
          </Field>
          <Field label="المفتاح (2–12 حرف لاتيني، بيبدأ بحرف)" hint={`مثال: ATLAS — التذاكر هتبقى ${(key || 'ATLAS').toUpperCase()}-1`}>
            <input
              className="input font-mono"
              required
              dir="ltr"
              minLength={2}
              maxLength={12}
              pattern="[A-Za-z][A-Za-z0-9]*"
              value={key}
              onChange={(e) => setKey(e.target.value.toUpperCase())}
              placeholder="ATLAS"
            />
          </Field>
          <Field label="وصف مختصر">
            <textarea className="input min-h-20" value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label="اللون">
            <div className="flex flex-wrap gap-2">
              {PALETTE.map((c) => (
                <button
                  key={c}
                  type="button"
                  aria-label={c}
                  onClick={() => setColor(c)}
                  className={`size-7 rounded-full ring-2 transition ${color === c ? 'ring-white' : 'ring-transparent'}`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </Field>
          {error && <p className="text-xs text-rose-300">{error}</p>}
        </form>
      </Modal>
    </div>
  )
}
