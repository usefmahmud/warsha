import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError, tokenStore } from './api/client'
import type { UserOut } from './api/types'

interface AuthValue {
  user: UserOut | null
  /** true while the stored token is being validated on boot */
  booting: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: { email: string; name: string; username: string; password: string }) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null)
  const [booting, setBooting] = useState(true)

  useEffect(() => {
    let alive = true
    const token = tokenStore.get()
    if (!token) {
      setBooting(false)
      return
    }
    api
      .me()
      .then((me) => {
        if (alive) setUser(me)
      })
      .catch(() => {
        tokenStore.clear()
      })
      .finally(() => {
        if (alive) setBooting(false)
      })
    return () => {
      alive = false
    }
  }, [])

  // Any 401 from anywhere in the app drops the session.
  useEffect(() => {
    const onUnauthorised = () => setUser(null)
    window.addEventListener('atlas:unauthorised', onUnauthorised)
    return () => window.removeEventListener('atlas:unauthorised', onUnauthorised)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const out = await api.login(email.trim().toLowerCase(), password)
    tokenStore.set(out.access_token)
    setUser(out.user)
  }, [])

  const register = useCallback(
    async (input: { email: string; name: string; username: string; password: string }) => {
      const out = await api.register({
        ...input,
        email: input.email.trim().toLowerCase(),
        username: input.username.trim().toLowerCase(),
      })
      tokenStore.set(out.access_token)
      setUser(out.user)
    },
    [],
  )

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  const value = useMemo<AuthValue>(
    () => ({ user, booting, login, register, logout }),
    [user, booting, login, register, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) return err.message
  return 'حصل خطأ غير متوقع'
}
