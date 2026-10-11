import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useData } from '@/shared/api'
import { fmt, date } from '@/shared/lib'
import type { MatchDetail, Insights } from '@/shared/api/contracts'
import { Title, Gate } from '@/shared/ui'
import { ArrowRight, Database, Swords, Activity } from 'lucide-react'
import { useSettings } from '@/entities/settings'
import { Status, Scoreboard, mapName, isMatchPending } from '@/entities/match'

export function MatchPage() {
  const { id } = useParams()
  const result = useData<MatchDetail>(`/api/matches/${id}`, isMatchPending)
  const m = result.data
  const notes = useData<{ steam_id64: string; notes: string[]; history: Insights }[]>(
    m?.status === 'ready' ? `/api/matches/${id}/insights` : null,
  )
  const [round, setRound] = useState(0)
  const { settings } = useSettings()
  const note = notes.data?.find((n) => n.steam_id64 === settings?.steam_id64) ?? notes.data?.[0]
  const player = m?.players.find((p) => p.steam_id64 === note?.steam_id64)
  return (
    <>
      <Link to="/matches" className="back-link">
        ← Все матчи
      </Link>
      <Title
        eyebrow={`ОТЧЁТ / ИМПОРТ #${id}`}
        title={m ? mapName(m.map_name) : 'Отчёт матча'}
        subtitle={
          m
            ? `Импортирован ${date(m.imported_at)} · дата игры: ${m.played_at ? date(m.played_at) : 'нет данных'}`
            : 'Получаем данные записи'
        }
      />
      <Gate {...result}>
        {m && (
          <>
            {m.status !== 'ready' ? (
              <section className="panel">
                <Status value={m.status} position={m.queue_position} />
                <p className={m.status === 'failed' ? 'error-text' : 'muted'}>
                  {m.error ??
                    (m.status === 'processing'
                      ? 'Считываем статистику из демки. Результат появится после завершения разбора.'
                      : 'Демка сохранена в общей очереди. Записи всех пользователей разбираются по одной.')}
                </p>
                {m.status === 'failed' && (
                  <Link to="/import" className="button primary">
                    Повторить загрузку
                  </Link>
                )}
              </section>
            ) : (
              <>
                <div className="match-banner">
                  <div>
                    <span className="eyebrow">КОМАНДА A</span>
                    <strong>{m.team_scores?.A ?? '—'}</strong>
                  </div>
                  <div className="match-banner-center">
                    <Swords size={22} />
                    <span>{m.rounds.length} завершённых раундов в записи</span>
                    <small>
                      {m.team_scores ? 'Подтверждённый итоговый счёт' : 'Итоговый счёт: нет данных'}
                    </small>
                  </div>
                  <div>
                    <span className="eyebrow blue">КОМАНДА B</span>
                    <strong>{m.team_scores?.B ?? '—'}</strong>
                  </div>
                </div>
                <section className="panel scoreboard-panel">
                  <div className="section-heading">
                    <div>
                      <h2>
                        Таблица участников <span className="count">{m.players.length}</span>
                      </h2>
                      <p>Рассчитано из импортированной записи · только завершённые раунды</p>
                    </div>
                    <span className="tag subtle">
                      <Database size={12} /> ИЗ ДЕМКИ
                    </span>
                  </div>
                  <Scoreboard players={m.players} mySteamId={settings?.steam_id64} />
                  <p className="table-note">
                    A/B — составы по первому подтверждённому участию; текущие стороны T/CT показаны
                    по раундам. «—» означает нет данных. Наведите курсор на показатель для причины.
                  </p>
                </section>
                <div className="detail-grid">
                  <section className="panel">
                    <div className="section-heading">
                      <div>
                        <h2>Разбор статистики</h2>
                        <p>
                          {player?.nickname ?? 'Заметки по игроку'}
                          {settings?.steam_id64 === player?.steam_id64 ? ' · ваш профиль' : ''}
                        </p>
                      </div>
                      <Activity size={20} />
                    </div>
                    <Gate {...notes}>
                      {note?.notes.map((n, i) => (
                        <div className="note-row" key={i}>
                          <span>{String(i + 1).padStart(2, '0')}</span>
                          <p>{n}</p>
                        </div>
                      ))}
                      {note && (
                        <Link className="text-link" to={`/players/${note.steam_id64}`}>
                          Полная история игрока <ArrowRight size={14} />
                        </Link>
                      )}
                    </Gate>
                  </section>
                  <section className="panel">
                    <div className="section-heading">
                      <div>
                        <h2>Раунды записи</h2>
                        <p>Стороны из состояния игры, включая овертайм</p>
                      </div>
                    </div>
                    <div className="round-strip">
                      {m.rounds.map((r, i) => (
                        <button
                          title={`Раунд ${r.number}, победа ${r.winning_side === 2 ? 'T' : 'CT'}`}
                          aria-pressed={i === round}
                          key={r.number}
                          className={`round-button side-${r.winning_side} ${i === round ? 'selected' : ''}`}
                          onClick={() => setRound(i)}
                        >
                          {r.number}
                        </button>
                      ))}
                    </div>
                    {m.rounds[round] && (
                      <>
                        <p className="muted tiny">
                          Раунд {m.rounds[round].number} · победа{' '}
                          {m.rounds[round].winning_side === 2 ? 'T' : 'CT'} · тики{' '}
                          {m.rounds[round].start_tick}–{m.rounds[round].end_tick}
                        </p>
                        <div className="round-players">
                          {Object.entries(m.rounds[round].players).map(([s, p]) => (
                            <div key={s}>
                              <Link to={`/players/${s}`}>
                                {m.players.find((pl) => pl.steam_id64 === s)?.nickname ?? s}
                              </Link>
                              <span>
                                {p.side === 2 ? 'T' : 'CT'} · {fmt(p.kills, 0)}K /{' '}
                                {fmt(p.deaths, 0)}D · урон {fmt(p.effective_damage, 0)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </section>
                </div>
              </>
            )}
            <details className="panel diagnostics">
              <summary>Диагностика и доступность данных</summary>
              <p>Версия парсера: demoparser2 {m.parser_version}</p>
              <ul>
                {m.diagnostics.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
              {m.players
                .filter((p) => p.missing_reasons.length)
                .map((p) => (
                  <p key={p.steam_id64}>
                    <strong>{p.nickname}:</strong> {p.missing_reasons.join('; ')}
                  </p>
                ))}
            </details>
          </>
        )}
      </Gate>
    </>
  )
}
