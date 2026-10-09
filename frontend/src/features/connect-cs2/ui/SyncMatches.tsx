import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '@/shared/api'
export function SyncMatches({
  pending = false,
  onQueued,
}: {
  pending?: boolean
  onQueued: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function sync() {
    setBusy(true)
    setError('')
    try {
      await api('/api/cs2/sync', { method: 'POST' })
      onQueued()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось обновить матчи')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div>
      <button className="button primary" disabled={pending || busy} onClick={() => void sync()}>
        <RefreshCw size={16} className={pending || busy ? 'spin' : ''} />
        {pending || busy ? 'Обновляем…' : 'Обновить матчи'}
      </button>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
    </div>
  )
}
