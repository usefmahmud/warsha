import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage, useAuth } from '../auth'

type Mode = 'login' | 'register'

export function LoginScreen() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isRegister = mode === 'register'

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      if (isRegister) {
        await register({ email, name, username, password })
      } else {
        await login(email, password)
      }
      navigate('/projects', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  function switchMode() {
    setMode(isRegister ? 'login' : 'register')
    setError(null)
  }

  return (
    <div className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span className="grid size-12 place-items-center rounded-2xl bg-brand-500 text-2xl font-black text-white shadow-xl shadow-brand-600/30">
            A
          </span>
          <h1 className="text-xl font-bold text-slate-100">
            {isRegister ? 'إنشاء حساب في Atlas' : 'أهلاً في Atlas'}
          </h1>
          <p className="text-xs text-slate-400">
            {isRegister ? 'أول حساب بيبقى مالك المساحة' : 'سجّل دخول بحسابك في الفريق'}
          </p>
        </div>

        <form onSubmit={onSubmit} className="card space-y-4 p-5">
          {isRegister && (
            <>
              <label className="block space-y-1.5">
                <span className="text-xs font-medium text-slate-300">الاسم</span>
                <input
                  className="input"
                  required
                  minLength={2}
                  placeholder="يوسف محمود"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>

              <label className="block space-y-1.5">
                <span className="text-xs font-medium text-slate-300">اسم المستخدم</span>
                <input
                  className="input"
                  required
                  minLength={3}
                  pattern="[a-zA-Z0-9_.-]+"
                  dir="ltr"
                  placeholder="youssef"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </label>
            </>
          )}

          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-slate-300">الإيميل</span>
            <input
              className="input"
              type="email"
              autoComplete="username"
              inputMode="email"
              required
              dir="ltr"
              placeholder="you@atlas.dev"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-slate-300">الباسورد</span>
            <input
              className="input"
              type="password"
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              required
              minLength={isRegister ? 8 : undefined}
              dir="ltr"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {isRegister && <span className="block text-[10px] text-slate-500">8 أحرف على الأقل</span>}
          </label>

          {error && (
            <p className="rounded-xl border border-rose-400/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
              {error}
            </p>
          )}

          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? 'لحظة…' : isRegister ? 'إنشاء الحساب' : 'دخول'}
          </button>

          <button
            type="button"
            onClick={switchMode}
            className="w-full rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
          >
            {isRegister ? 'عندي حساب بالفعل — دخول' : 'معنديش حساب — إنشاء حساب جديد'}
          </button>
        </form>

        <p className="mt-4 text-center text-[11px] text-slate-500">
          أول حساب في المساحة بيبقى المالك. باقي الحسابات بيضيفها الأدمن.
        </p>
      </div>
    </div>
  )
}
