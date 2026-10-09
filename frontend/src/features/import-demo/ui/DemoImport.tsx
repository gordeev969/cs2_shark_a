import { isSnapshotMode } from '@/shared/config'
import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useData, getCSRFToken } from '@/shared/api'
import type { Health, MatchDetail } from '@/shared/api/contracts'
import { Gate, ReadonlyNotice } from '@/shared/ui'
import { fmt } from '@/shared/lib'
import { Status, mapName, isMatchPending } from '@/entities/match'
import {
  ArrowDownToLine,
  LockKeyhole,
  LoaderCircle,
  ArrowRight,
  ShieldCheck,
  FileUp,
} from 'lucide-react'

export function DemoImport() {
  return isSnapshotMode ? <ReadonlyNotice /> : <NativeDemoImport />
}

function NativeDemoImport() {
  const health = useData<Health>('/api/health')
  const [file, setFile] = useState<File | null>(null)
  const [id, setId] = useState<number | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [duplicate, setDuplicate] = useState(false)
  const [dragging, setDragging] = useState(false)
  const xhrRef = useRef<XMLHttpRequest | null>(null)
  const job = useData<MatchDetail>(id ? `/api/matches/${id}` : null, isMatchPending)
  useEffect(() => () => xhrRef.current?.abort(), [])
  const limit = health.data?.max_upload_bytes
  const busy =
    progress !== null || job.data?.status === 'queued' || job.data?.status === 'processing'

  function selectFile(candidate?: File) {
    if (!candidate || busy) return
    setError('')
    setId(null)
    setDuplicate(false)
    if (!candidate.name.toLowerCase().endsWith('.dem')) {
      setFile(null)
      setError('Выберите несжатую демку .dem. Архив необходимо распаковать.')
      return
    }
    if (limit && candidate.size > limit) {
      setFile(null)
      setError(`Лимит файла — ${Math.floor(limit / 1024 / 1024)} МБ.`)
      return
    }
    setFile(candidate)
  }

  function upload() {
    if (!file || !limit || busy) return
    setError('')
    setProgress(0)
    setId(null)
    const xhr = new XMLHttpRequest()
    xhrRef.current = xhr
    xhr.open('POST', '/api/matches/import')
    const csrf = getCSRFToken()
    if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf)
    xhr.responseType = 'json'
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      setProgress(null)
      if (xhr.status >= 200 && xhr.status < 300 && typeof xhr.response?.id === 'number') {
        setId(xhr.response.id)
        setDuplicate(xhr.response.duplicate)
      } else
        setError(
          typeof xhr.response?.detail === 'string'
            ? xhr.response.detail
            : `Не удалось загрузить файл (${xhr.status}).`,
        )
    }
    xhr.onerror = () => {
      setProgress(null)
      setError('Нет подключения к локальному API. Проверьте, что backend запущен.')
    }
    xhr.ontimeout = () => {
      setProgress(null)
      setError('Загрузка прервана по таймауту. Повторите импорт.')
    }
    xhr.timeout = 300000
    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  }

  return (
    <>
      <div className="import-grid">
        <section className="panel import-panel">
          <Gate {...health}>
            <div className="section-heading">
              <h2>Загрузка записи</h2>
              <span className="tag subtle">.DEM</span>
            </div>
            <label
              htmlFor="demo-file"
              className={`dropzone ${dragging ? 'dragging' : ''} ${busy ? 'disabled' : ''}`}
              onDragOver={(e) => {
                e.preventDefault()
                if (!busy) setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                selectFile(e.dataTransfer.files[0])
              }}
            >
              <div className="upload-icon">
                <ArrowDownToLine size={30} />
              </div>
              <strong>{file ? file.name : 'Перетащите демку сюда'}</strong>
              <span>
                {file
                  ? `${fmt(file.size / 1024 / 1024, 1)} МБ · готова к загрузке`
                  : 'или нажмите, чтобы выбрать файл'}
              </span>
              <small>Несжатый .dem · до {limit ? Math.floor(limit / 1024 / 1024) : '…'} МБ</small>
              <input
                id="demo-file"
                aria-label="Выбрать демку"
                className="sr-only"
                type="file"
                accept=".dem"
                disabled={!!busy}
                onChange={(e) => selectFile(e.target.files?.[0])}
              />
            </label>
            {error && (
              <p role="alert" className="error-box">
                {error}
              </p>
            )}
            {progress !== null && (
              <div className="upload-progress" role="status">
                <div>
                  <span>Передача в локальный анализатор</span>
                  <strong>{progress}%</strong>
                </div>
                <progress max={100} value={progress} />
              </div>
            )}
            {id && (
              <Gate {...job}>
                {job.data && (
                  <div className={`job-result ${job.data.status}`} role="status">
                    <Status value={job.data.status} />
                    {duplicate && (
                      <p>Эта демка уже есть в базе. Повторная статистика не создана.</p>
                    )}
                    {job.data.status === 'processing' || job.data.status === 'queued' ? (
                      <p>Разбираем запись. Можно перейти в библиотеку — обработка продолжится.</p>
                    ) : job.data.status === 'failed' ? (
                      <p className="error-text">{job.data.error}</p>
                    ) : (
                      <p>
                        {mapName(job.data.map_name)} · {job.data.players.length} игроков ·{' '}
                        {job.data.rounds.length} завершённых раундов
                      </p>
                    )}
                    <Link className="text-link" to={`/matches/${id}`}>
                      {job.data.status === 'ready' ? 'Открыть отчёт' : 'Открыть импорт'}{' '}
                      <ArrowRight size={15} />
                    </Link>
                  </div>
                )}
              </Gate>
            )}
            <button
              className="button primary full"
              disabled={!file || !limit || !!busy}
              onClick={upload}
            >
              {busy ? <LoaderCircle size={17} className="spin" /> : <FileUp size={17} />}
              {busy
                ? 'Обрабатываем запись…'
                : job.data?.status === 'failed'
                  ? 'Повторить импорт'
                  : 'Загрузить и разобрать'}
            </button>
            <p className="muted tiny centered">
              <LockKeyhole size={12} /> Файл обрабатывается на этом компьютере
            </p>
          </Gate>
        </section>
        <aside className="import-help">
          <section className="panel">
            <h2>Откуда взять демку?</h2>
            <ol className="steps">
              <li>
                <span>01</span>
                <div>
                  <strong>Откройте CS2</strong>
                  <p>Перейдите в просмотр своих недавних матчей.</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>Скачайте запись матча</strong>
                  <p>Используйте доступную в игре загрузку демки своего матча.</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>Выберите файл .dem</strong>
                  <p>
                    Записи обычно находятся в папке csgo/replays. Если скачан .bz2, сначала
                    распакуйте его.
                  </p>
                </div>
              </li>
            </ol>
          </section>
          <div className="privacy-note">
            <ShieldCheck size={22} />
            <div>
              <strong>Ваши данные остаются у вас</strong>
              <p>
                Статистика хранится локально и не отправляется в AI.{' '}
                {health.data?.retain_demos
                  ? 'Копии демок сохраняются локально.'
                  : 'Копия демки удаляется после обработки; статистика остаётся в SQLite.'}
              </p>
            </div>
          </div>
        </aside>
      </div>
    </>
  )
}
