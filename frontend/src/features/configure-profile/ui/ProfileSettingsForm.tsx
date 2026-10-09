import { isSnapshotMode } from '@/shared/config'
import { useEffect, useState, type FormEvent } from 'react'
import { Check, CheckCircle2, LoaderCircle } from 'lucide-react'
import { useAuth } from '@/entities/auth'
import { saveSettings, useSettings } from '@/entities/settings'

export function ProfileSettingsForm() {
  const { authenticated } = useAuth()
  const { settings, refresh } = useSettings()
  const [steam, setSteam] = useState(settings?.steam_id64 ?? '')
  const [compact, setCompact] = useState(settings?.compact ?? false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (settings) {
      setSteam(settings.steam_id64)
      setCompact(settings.compact)
    }
  }, [settings])

  async function save(e: FormEvent) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (steam && !/^\d{17}$/.test(steam)) {
      setError('SteamID64 должен содержать 17 цифр. Можно оставить поле пустым.')
      return
    }
    setSaving(true)
    try {
      await saveSettings(steam, compact)
      setMessage('Настройки сохранены локально')
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(e) => void save(e)}>
      <label className="form-label" htmlFor="steam">
        {isSnapshotMode ? 'SteamID64 выбранного игрока' : 'Ваш SteamID64'}
      </label>
      <input
        className="form-input"
        id="steam"
        readOnly={authenticated}
        inputMode="numeric"
        maxLength={17}
        placeholder="17 цифр, необязательно"
        value={steam}
        onChange={(e) => setSteam(e.target.value.trim())}
      />
      <p className="muted tiny">
        {isSnapshotMode
          ? 'Выберите участника контрольной демки в его профиле. Выбор сохраняется только в вашем браузере.'
          : authenticated
            ? 'SteamID подтверждён входом через Steam.'
            : 'Стабильный идентификатор из демки. Можно нажать «Это я» в профиле игрока.'}
      </p>
      <label className="checkbox-row">
        <div>
          <strong>Компактные таблицы</strong>
          <span>Уменьшить расстояние между строками</span>
        </div>
        <input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} />
      </label>
      {error && (
        <p className="error-box" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="success-text" role="status">
          <CheckCircle2 size={16} /> {message}
        </p>
      )}
      <button className="button primary" disabled={saving}>
        {saving ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}Сохранить
        настройки
      </button>
    </form>
  )
}
