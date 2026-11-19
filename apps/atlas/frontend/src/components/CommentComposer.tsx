import { useMemo, useRef, useState } from 'react'
import { useAuth } from '../auth'
import type { MemberOut } from '../api/types'
import { Avatar } from './ui'

interface Props {
  members: MemberOut[]
  onSubmit: (body: string) => Promise<void>
  placeholder?: string
}

/**
 * Comment box with @mention autocomplete over the project members.
 * Typing "@" (or "@om") opens a filtered list; picking a row inserts "@username ".
 */
export function CommentComposer({ members, onSubmit, placeholder = 'اكتب كومنت… استخدم @ لمنشن حد' }: Props) {
  const { user } = useAuth()
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState<string | null>(null)
  const ref = useRef<HTMLTextAreaElement>(null)

  const suggestions = useMemo(() => {
    if (query === null) return []
    const q = query.toLowerCase()
    return members
      .filter((m) => m.user.id !== user?.id)
      .filter((m) => !q || m.user.username.toLowerCase().includes(q) || m.user.full_name.toLowerCase().includes(q))
      .slice(0, 6)
  }, [members, query, user?.id])

  function onChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const next = e.target.value
    setValue(next)
    const caret = e.target.selectionStart ?? next.length
    const before = next.slice(0, caret)
    const match = /@([A-Za-z0-9_.-]*)$/.exec(before)
    setQuery(match ? match[1] : null)
  }

  function pick(username: string) {
    const el = ref.current
    const caret = el?.selectionStart ?? value.length
    const before = value.slice(0, caret).replace(/@([A-Za-z0-9_.-]*)$/, `@${username} `)
    const after = value.slice(caret)
    const next = before + after
    setValue(next)
    setQuery(null)
    requestAnimationFrame(() => {
      el?.focus()
      el?.setSelectionRange(before.length, before.length)
    })
  }

  async function submit() {
    const body = value.trim()
    if (!body || busy) return
    setBusy(true)
    setError(null)
    try {
      await onSubmit(body)
      setValue('')
      setQuery(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'مش قادر أضيف الكومنت')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative">
      <textarea
        ref={ref}
        className="input min-h-24 resize-y"
        value={value}
        placeholder={placeholder}
        onChange={onChange}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault()
            void submit()
          }
          if (e.key === 'Escape') setQuery(null)
        }}
        onBlur={() => window.setTimeout(() => setQuery(null), 150)}
      />

      {query !== null && suggestions.length > 0 && (
        <ul className="absolute inset-x-2 bottom-full z-20 mb-1 max-h-52 overflow-auto rounded-xl border border-white/10 bg-ink-800 p-1 shadow-2xl">
          {suggestions.map((m) => (
            <li key={m.user.id}>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-start text-xs text-slate-200 hover:bg-white/8"
                onClick={() => pick(m.user.username)}
              >
                <Avatar user={m.user} size={20} />
                <span className="font-medium">{m.user.full_name || m.user.username}</span>
                <span className="text-slate-500">@{m.user.username}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[11px] text-slate-500">Ctrl+Enter للإرسال · @ لمنشن</span>
        <button type="button" className="btn-primary !py-1.5" onClick={submit} disabled={busy || !value.trim()}>
          {busy ? 'بيبعت…' : 'إرسال'}
        </button>
      </div>
      {error && <p className="mt-1 text-[11px] text-rose-300">{error}</p>}
    </div>
  )
}
