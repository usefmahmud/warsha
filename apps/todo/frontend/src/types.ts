export type Priority = 'low' | 'normal' | 'high'

export interface Todo {
  id: string
  title: string
  notes: string | null
  done: boolean
  priority: Priority
  created_at: string
  updated_at: string
  due_date: string | null
}

export interface TodoList {
  items: Todo[]
  count: number
  open_count: number
  done_count: number
}

export interface TodoCreate {
  title: string
  notes?: string | null
  priority?: Priority
  due_date?: string | null
}

export type TodoPatch = Partial<Omit<TodoCreate, 'title'>> & { title?: string; done?: boolean }

export type Filter = 'all' | 'open' | 'done'
