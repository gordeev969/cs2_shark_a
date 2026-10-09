import { isSnapshotMode } from '@/shared/config'
import { ArrowRight, LogOut } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/shared/api'
import { ReadonlyNotice } from '@/shared/ui'
import { useAuth } from '@/entities/auth'
export function SteamSignIn() {
  if (isSnapshotMode) return <ReadonlyNotice />
  return (
    <a className="button primary steam-login" href="/api/auth/steam/login">
      Войти через Steam <ArrowRight size={18} />
    </a>
  )
}
export function SteamSignOut() {
  const { refresh } = useAuth()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function logout() {
    setBusy(true)
    setError('')
    try {
      await api('/api/auth/logout', { method: 'POST' })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось выйти')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      <button className="button secondary" disabled={busy} onClick={() => void logout()}>
        <LogOut size={15} />
        Выйти
      </button>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
    </div>
  )
}
