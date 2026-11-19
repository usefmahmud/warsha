import { useEffect, useState } from 'react'
import { api } from '../api/client'
import {
  PRIORITY_LABEL,
  STATUS_LABEL,
  STATUS_ORDER,
  TYPE_LABEL,
  type MemberOut,
  type TicketOut,
  type TicketPriority,
  type TicketStatus,
  type TicketType,
} from '../api/types'
import { errorMessage } from '../auth'
import { Field, Modal } from './ui'

const TYPES: TicketType[] = ['task', 'bug', 'story', 'chore']
const PRIORITIES: TicketPriority[] = ['urgent', 'high', 'normal', 'low']

interface Props {
  open: boolean
  projectKey: string
  members: MemberOut[]
  defaultStatus?: TicketStatus
  onClose: () => void
  onCreated: (ticket: TicketOut) => void
}

export function NewTicketModal({ open, projectKey, members, defaultStatus = 'todo', onClose, onCreated }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [type, setType] = useState<TicketType>('task')
  const [priority, setPriority] = useState<TicketPriority>('normal')
  const [status, setStatus] = useState<TicketStatus>(defaultStatus)
  const [assignee, setAssignee] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setStatus(defaultStatus)
      setError(null)
    }
  }, [open, defaultStatus])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (busy || !title.trim()) return
    setBusy(true)
    setError(null)
    try {
      const created = await api.createTicket({
        project_key: projectKey,
        title: title.trim(),
        description,
        type,
        priority,
        status,
        assignee_username: assignee || undefined,
        due_date: dueDate || undefined,
      })
      onCreated(created)
      setTitle('')
      setDescription('')
      setDueDate('')
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      title="تذكرة جديدة"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            إلغاء
          </button>
          <button type="submit" form="new-ticket" className="btn-primary" disabled={busy || !title.trim()}>
            {busy ? 'بيضيف…' : 'إضافة'}
          </button>
        </>
      }
    >
      <form id="new-ticket" onSubmit={submit} className="space-y-3">
        <Field label="العنوان">
          <input className="input" required autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="إيه المطلوب بالظبط؟" />
        </Field>
        <Field label="الوصف">
          <textarea className="input min-h-24" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="تفاصيل، خطوات إعادة الإنتاج، معايير القبول…" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="النوع">
            <select className="input" value={type} onChange={(e) => setType(e.target.value as TicketType)}>
              {TYPES.map((t) => (
                <option key={t} value={t}>{TYPE_LABEL[t]}</option>
              ))}
            </select>
          </Field>
          <Field label="الأولوية">
            <select className="input" value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>
              ))}
            </select>
          </Field>
          <Field label="الحالة">
            <select className="input" value={status} onChange={(e) => setStatus(e.target.value as TicketStatus)}>
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>{STATUS_LABEL[s]}</option>
              ))}
            </select>
          </Field>
          <Field label="المسؤول">
            <select className="input" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              <option value="">بدون</option>
              {members.map((m) => (
                <option key={m.user.id} value={m.user.username}>
                  {m.user.full_name || m.user.username}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="تاريخ الاستحقاق">
          <input className="input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </Field>
        {error && <p className="text-xs text-rose-300">{error}</p>}
      </form>
    </Modal>
  )
}
