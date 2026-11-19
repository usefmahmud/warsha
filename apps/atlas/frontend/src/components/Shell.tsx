import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Avatar } from './ui'

interface NavItem {
  to: string
  label: string
  icon: string
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/projects', label: 'المشاريع', icon: '◧', end: true },
  { to: '/my', label: 'شغلي', icon: '◎' },
]

export function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-s border-white/8 bg-ink-850/70 p-4 backdrop-blur md:flex">
        <button
          type="button"
          onClick={() => navigate('/projects')}
          className="mb-6 flex items-center gap-2.5 text-start"
        >
          <span className="grid size-9 place-items-center rounded-xl bg-brand-500 text-lg font-black text-white shadow-lg shadow-brand-600/30">
            A
          </span>
          <span>
            <span className="block text-sm font-bold text-slate-100">Atlas</span>
            <span className="block text-[11px] text-slate-500">إدارة المشاريع والتذاكر</span>
          </span>
        </button>

        <nav className="space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition ${
                  isActive
                    ? 'bg-brand-500/15 text-brand-300 ring-1 ring-brand-400/25'
                    : 'text-slate-300 hover:bg-white/6'
                }`
              }
            >
              <span className="text-base opacity-80">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-3 border-t border-white/8 pt-3">
          <div className="flex items-center gap-2.5">
            <Avatar user={user} size={32} />
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-slate-200">{user?.full_name || user?.username}</p>
              <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
            </div>
          </div>
          <button type="button" className="btn-ghost w-full !py-1.5 !text-xs" onClick={logout}>
            خروج
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-white/8 bg-ink-900/80 px-4 py-2.5 backdrop-blur md:hidden">
          <Avatar user={user} size={26} />
          <nav className="flex flex-1 gap-1 overflow-x-auto">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-lg px-2.5 py-1 text-xs whitespace-nowrap ${
                    isActive ? 'bg-brand-500/20 text-brand-200' : 'text-slate-300'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <button type="button" className="btn-ghost !px-2 !py-1 !text-xs" onClick={logout}>
            خروج
          </button>
        </header>
        <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  )
}
