import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { AuthContext } from '@/entities/auth'
import { api, setCSRFToken } from '@/shared/api'
import { isSnapshotMode } from '@/shared/config'
import type { AuthSession } from '@/shared/api/contracts'
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    if (isSnapshotMode) {
      setSession({ authenticated: false, required: false, user: null, csrf_token: null })
      setCSRFToken(null)
      return
    }
    try {
      const data = await api<AuthSession>('/api/auth/session')
      setCSRFToken(data.csrf_token)
      setSession(data)
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Нет подключения к API')
    }
  }, [])
  useEffect(() => {
    void refresh()
    const expired = () => {
      void refresh()
    }
    window.addEventListener('cs2-session-expired', expired)
    return () => window.removeEventListener('cs2-session-expired', expired)
  }, [refresh])
  if (error)
    return (
      <div className="auth-stage">
        <section className="panel">
          <p role="alert">{error}</p>
          <button className="button primary" onClick={() => void refresh()}>
            Повторить подключение
          </button>
        </section>
      </div>
    )
  if (!session)
    return (
      <div className="loading" role="status">
        Подключаем ваше пространство…
      </div>
    )
  return <AuthContext.Provider value={{ ...session, refresh }}>{children}</AuthContext.Provider>
}
