import { isSnapshotMode } from '@/shared/config'
import { useState } from 'react'
import { Check, Target, LoaderCircle } from 'lucide-react'
import { useAuth } from '@/entities/auth'
import { saveSettings, useSettings } from '@/entities/settings'

export function SelectOwnPlayer({ steamId }: { steamId: string }) {
  const { authenticated } = useAuth()
  const { settings, refresh } = useSettings()
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const selected = settings?.steam_id64 === steamId

  async function select() {
    setSaving(true)
    setError('')
    try {
      await saveSettings(steamId, settings?.compact ?? false)
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить профиль')
    } finally {
      setSaving(false)
    }
  }

  if (authenticated && !selected) return null

  return (
    <div className="select-own">
      <button
        className="button secondary"
        disabled={saving || selected}
        onClick={() => void select()}
      >
        {saving ? (
          <LoaderCircle size={15} className="spin" />
        ) : selected ? (
          <Check size={15} />
        ) : (
          <Target size={15} />
        )}
        {isSnapshotMode
          ? selected
            ? 'Выбранный игрок'
            : 'Выбрать игрока'
          : selected
            ? 'Ваш профиль'
            : 'Это я'}
      </button>
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
