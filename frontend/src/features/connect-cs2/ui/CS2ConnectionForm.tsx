import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { KeyRound, RefreshCw, Unplug, CheckCircle2 } from 'lucide-react'
import { api, useData } from '@/shared/api'
import type { CS2Connection } from '@/shared/api/contracts'
import { Gate } from '@/shared/ui'
import { connectionStatus, isSyncPending } from '@/entities/cs2-connection'
import { date } from '@/shared/lib'
export function CS2ConnectionForm() {
  const navigate = useNavigate()
  const data = useData<CS2Connection>('/api/cs2/connection', isSyncPending)
  const [code, setCode] = useState('')
  const [sharing, setSharing] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const connection = data.data
  const working = busy || !!(connection && isSyncPending(connection))
  async function request(url: string, method: string, body?: object) {
    setBusy(true)
    setError('')
    try {
      await api<CS2Connection>(url, {
        method,
        ...(body
          ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
          : {}),
      })
      setCode('')
      data.retry()
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось подключиться')
      return false
    } finally {
      setBusy(false)
    }
  }
  async function connect(e: FormEvent) {
    e.preventDefault()
    const saved = await request('/api/cs2/connection', 'POST', {
      auth_code: code,
      sharing_code: sharing,
    })
    if (saved && connection?.steam_api_configured && connection.gc_configured) {
      await request('/api/cs2/sync', 'POST')
      navigate('/')
    }
  }
  return (
    <Gate {...data}>
      {connection && (
        <div className="connect-grid">
          <section className="panel">
            <div className="section-heading">
              <h2>Доступ к истории CS2</h2>
              <KeyRound size={20} />
            </div>
            {connection.connected && (
              <p className="success-text">
                <CheckCircle2 size={16} />
                Код доступа сохранён
              </p>
            )}
            <form onSubmit={(e) => void connect(e)}>
              <label htmlFor="auth-code" className="form-label">
                Game Authentication Code
              </label>
              <input
                id="auth-code"
                className="form-input"
                type="password"
                autoComplete="off"
                placeholder="XXXX-XXXX-XXXX"
                maxLength={32}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                disabled={working}
              />
              <p className="muted tiny">
                Получите код на{' '}
                <a
                  className="text-link"
                  href="https://steamcommunity.com/my/gcpd/730/?tab=accountmain"
                  target="_blank"
                  rel="noreferrer"
                >
                  странице личных данных CS2 в Steam
                </a>
                . Это код доступа к матчам, а не Steam Guard.
              </p>
              <label htmlFor="sharing-code" className="form-label">
                Код недавнего матча
              </label>
              <input
                id="sharing-code"
                className="form-input"
                autoComplete="off"
                placeholder="CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx"
                maxLength={64}
                value={sharing}
                onChange={(e) => setSharing(e.target.value)}
                required
                disabled={working}
              />
              <p className="muted tiny">
                В CS2 откройте недавний матч → «Поделиться». Загрузим этот матч и доступные записи
                после него; Valve не отдаёт всю старую историю.
              </p>
              <button className="button primary" disabled={working}>
                <KeyRound size={16} />
                {connection.connected ? 'Обновить доступ' : 'Подключить CS2'}
              </button>
            </form>
            {error && (
              <p className="error-box" role="alert">
                {error}
              </p>
            )}
          </section>
          <section className="panel sync-panel">
            <div className="section-heading">
              <h2>Синхронизация</h2>
              <span className="tag subtle">{connectionStatus(connection.status)}</span>
            </div>
            <p className="muted">
              Найдём коды матчей, скачаем доступные демки Valve и рассчитаем статистику.
            </p>
            <div className="sync-counts">
              <div>
                <strong>{connection.discovered_count}</strong>
                <span>Найдено</span>
              </div>
              <div>
                <strong>{connection.imported_count}</strong>
                <span>Разобрано</span>
              </div>
              <div>
                <strong>{connection.pending_count}</strong>
                <span>Ожидают</span>
              </div>
            </div>
            {connection.last_sync && (
              <p className="muted tiny">Последняя попытка: {date(connection.last_sync)}</p>
            )}
            {(!connection.steam_api_configured || !connection.gc_configured) && (
              <div className="notice">
                <strong>Автозагрузка пока не настроена</strong>
                <p>
                  {!connection.steam_api_configured && 'На сервере нужен ключ Steam Web API. '}
                  {!connection.gc_configured &&
                    'Для получения демок требуется подключение Steam к сервису Game Coordinator. '}
                  Можно начать с{' '}
                  <Link className="text-link" to="/import">
                    ручного импорта демки
                  </Link>
                  .
                </p>
              </div>
            )}
            {connection.error && (
              <p className="error-box" role="status">
                {connection.error}
              </p>
            )}
            <div className="button-row">
              <button
                className="button primary"
                disabled={working || !connection.connected}
                onClick={() => void request('/api/cs2/sync', 'POST')}
              >
                <RefreshCw size={16} className={working ? 'spin' : ''} />
                {working ? 'Обрабатываем…' : 'Загрузить матчи'}
              </button>
              {connection.connected && (
                <button
                  className="button secondary"
                  disabled={working}
                  onClick={() => void request('/api/cs2/connection', 'DELETE')}
                >
                  <Unplug size={16} />
                  Отключить
                </button>
              )}
            </div>
            <p className="muted tiny">
              Код доступа хранится зашифрованным. Отключение удаляет код; уже разобранные матчи
              остаются.
            </p>
            <Link to="/" className="text-link">
              Перейти к дашборду →
            </Link>
          </section>
        </div>
      )}
    </Gate>
  )
}
