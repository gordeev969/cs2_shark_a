import { isSnapshotMode } from '@/shared/config'
import { Link, useParams } from 'react-router-dom'
import { useData } from '@/shared/api'
import { fmt, date } from '@/shared/lib'
import type { Profile } from '@/shared/api/contracts'
import { Gate, Avatar } from '@/shared/ui'
import { Crosshair } from 'lucide-react'
import { useSettings } from '@/entities/settings'
import { mapName } from '@/entities/match'
import { HistoryNotes } from '@/entities/player'
import { SelectOwnPlayer } from '@/features/select-own-player'
import { StatCards } from '@/widgets/player-stats'
import { Trend } from '@/widgets/player-history'

export function PlayerPage() {
  const { steamId } = useParams()
  const result = useData<Profile>(`/api/players/${steamId}`)
  const p = result.data
  const { settings } = useSettings()
  return (
    <>
      <Link to="/players" className="back-link">
        ← Все игроки
      </Link>
      <Gate {...result}>
        {p && (
          <>
            <div className="profile-header">
              <Avatar name={p.latest_nickname} />
              <div>
                <div className="eyebrow">
                  {isSnapshotMode ? 'ПРОФИЛЬ УЧАСТНИКА' : 'ЛОКАЛЬНЫЙ ПРОФИЛЬ'}{' '}
                  {settings?.steam_id64 === p.steam_id64
                    ? isSnapshotMode
                      ? '/ ВЫБРАН'
                      : '/ ВЫ'
                    : ''}
                </div>
                <h1>{p.latest_nickname}</h1>
                <code>{p.steam_id64}</code>
              </div>
              <SelectOwnPlayer steamId={p.steam_id64} />
            </div>
            <StatCards summary={p.summary} />
            <div className="detail-grid">
              <Trend profile={p} />
              <section className="panel">
                <HistoryNotes insights={p.insights} />
              </section>
            </div>
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>История игрока</h2>
                  <p>Средние считаются по суммам урона и раундов, K/D — по суммам K и D</p>
                </div>
                <span className="count">{p.history.length}</span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Матч</th>
                      <th>Время импорта</th>
                      <th>K / D / A</th>
                      <th>K/D</th>
                      <th>ADR</th>
                      <th>HS%</th>
                      <th>Раунды</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.history.map((h) => (
                      <tr key={h.match_id}>
                        <td>
                          <Link to={`/matches/${h.match_id}`}>
                            {mapName(h.map_name)} <span className="muted">#{h.match_id}</span>
                          </Link>
                        </td>
                        <td className="muted">{date(h.imported_at)}</td>
                        <td>
                          {fmt(h.kills, 0)} / {fmt(h.deaths, 0)} / {fmt(h.assists, 0)}
                        </td>
                        <td className="metric-highlight">{fmt(h.kd, 2)}</td>
                        <td>{fmt(h.adr, 1)}</td>
                        <td>{fmt(h.hs_percent, 1)}</td>
                        <td>{fmt(h.rounds_played, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>Показатели по картам</h2>
                  <p>От трёх локально наблюдаемых матчей на карте</p>
                </div>
              </div>
              {p.map_splits.length ? (
                <div className="map-splits">
                  {p.map_splits.map((s) => (
                    <div className="map-split" key={s.map_name}>
                      <Crosshair size={20} />
                      <strong>{mapName(s.map_name)}</strong>
                      <span>{s.matches} матчей</span>
                      <span>K/D {fmt(s.kd, 2)}</span>
                      <span>
                        ADR {fmt(s.adr, 1)} ({s.adr_matches} матчей)
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">
                  Недостаточно матчей для разбивки по картам. Статистика появится после трёх
                  импортов с одной карты.
                </p>
              )}
            </section>
          </>
        )}
      </Gate>
    </>
  )
}
