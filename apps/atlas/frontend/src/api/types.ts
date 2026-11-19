// Types mirror the backend Pydantic schemas (app/schemas.py).
// Keep this file dependency-free: it is the contract with the API.

export type Id = string | number

export type UserRole = 'owner' | 'admin' | 'member'
export type ProjectRole = 'owner' | 'admin' | 'member'
export type TicketType = 'task' | 'bug' | 'story' | 'chore'
export type TicketPriority = 'urgent' | 'high' | 'normal' | 'low'
export type TicketStatus =
  | 'backlog'
  | 'todo'
  | 'in_progress'
  | 'review'
  | 'done'
  | 'blocked'

export interface UserBrief {
  id: Id
  username: string
  full_name: string
  avatar_url?: string | null
  color: string
}

export interface UserOut extends UserBrief {
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface TokenOut {
  access_token: string
  token_type: string
  expires_in: number
  user: UserOut
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface ProjectOut {
  id: Id
  key: string
  name: string
  description: string
  color: string
  owner?: UserBrief | null
  is_archived: boolean
  ticket_count: number
  member_count: number
  created_at: string
  updated_at: string
}

export interface MemberOut {
  user: UserBrief
  role: ProjectRole
  joined_at: string
}

export interface ProjectDetail extends ProjectOut {
  members?: MemberOut[]
  labels?: LabelOut[]
}

export interface LabelOut {
  id: Id
  name: string
  color: string
  project_id: Id
}

export interface Attachment {
  name: string
  url: string
}

export interface TicketOut {
  id: Id
  key: string
  project_id: Id
  project_key: string
  number: number
  title: string
  description: string
  type: TicketType
  priority: TicketPriority
  status: TicketStatus
  assignee?: UserBrief | null
  reporter?: UserBrief | null
  parent_id?: Id | null
  parent_key?: string | null
  due_date?: string | null
  points?: number | null
  position: number
  attachments?: Attachment[]
  labels?: LabelOut[]
  comment_count?: number
  subtask_count?: number
  created_at: string
  updated_at: string
  closed_at?: string | null
}

export interface CommentOut {
  id: Id
  ticket_id: Id
  ticket_key: string
  author: UserBrief
  body: string
  edited: boolean
  mentions?: string[]
  created_at: string
  updated_at: string
}

export interface ActivityOut {
  id: Id
  project_id: Id
  ticket_id?: Id | null
  ticket_key?: string | null
  actor?: UserBrief | null
  action: string
  field?: string | null
  old_value?: string | null
  new_value?: string | null
  created_at: string
}

export interface NotificationOut {
  id: Id
  type: string
  message: string
  is_read: boolean
  actor?: UserBrief | null
  ticket_id?: Id | null
  ticket_key?: string | null
  created_at: string
}

export interface BoardColumn {
  status: TicketStatus
  tickets: TicketOut[]
}

export interface BoardOut {
  project: ProjectOut
  columns: BoardColumn[]
}

export interface MyWorkOut {
  assigned: TicketOut[]
  mentions: NotificationOut[]
}

export interface TicketCreateInput {
  project_id?: number
  project_key?: string
  title: string
  description?: string
  type?: TicketType
  priority?: TicketPriority
  status?: TicketStatus
  assignee_id?: Id | null
  assignee_username?: string
  due_date?: string | null
  labels?: string[]
}

export const STATUS_LABEL: Record<TicketStatus, string> = {
  backlog: 'الأفكار',
  todo: 'قائمة الانتظار',
  in_progress: 'شغّال',
  review: 'مراجعة',
  done: 'خلص',
  blocked: 'متوقف',
}

export const STATUS_ORDER: TicketStatus[] = [
  'backlog',
  'todo',
  'in_progress',
  'review',
  'done',
  'blocked',
]

export const STATUS_STYLE: Record<TicketStatus, string> = {
  backlog: 'bg-slate-500/15 text-slate-300 border-slate-400/20',
  todo: 'bg-sky-500/15 text-sky-300 border-sky-400/20',
  in_progress: 'bg-amber-500/15 text-amber-300 border-amber-400/20',
  review: 'bg-violet-500/15 text-violet-300 border-violet-400/20',
  done: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/20',
  blocked: 'bg-rose-500/15 text-rose-300 border-rose-400/20',
}

export const PRIORITY_LABEL: Record<TicketPriority, string> = {
  urgent: 'عاجل',
  high: 'مهم',
  normal: 'عادي',
  low: 'منخفض',
}

export const PRIORITY_STYLE: Record<TicketPriority, string> = {
  urgent: 'bg-rose-500/15 text-rose-300 border-rose-400/30',
  high: 'bg-orange-500/15 text-orange-300 border-orange-400/30',
  normal: 'bg-slate-500/15 text-slate-300 border-slate-400/20',
  low: 'bg-slate-600/15 text-slate-400 border-slate-500/20',
}

export const TYPE_LABEL: Record<TicketType, string> = {
  task: 'مهمة',
  bug: 'باج',
  story: 'قصة',
  chore: 'روتين',
}
