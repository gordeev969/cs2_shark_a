import { Link } from 'react-router-dom'
import type { Participant } from '@/shared/api/contracts'
import { Avatar } from '@/shared/ui'
import { fmt } from '@/shared/lib'

export function Scoreboard({ players, mySteamId }: { players: Participant[]; mySteamId?: string }) {
  return (
    <div className="table-scroll">
      <table className="scoreboard">
        <thead>
          <tr>
            <th>Игрок</th>
            <th>Команда</th>
            <th title="Убийства противников">K</th>
            <th title="Все смерти">D</th>
            <th title="Игровые ассисты">A</th>
            <th>K/D</th>
            <th>ADR</th>
            <th>HS%</th>
            <th>K/R</th>
            <th>Раунды</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <tr key={p.steam_id64} className={p.steam_id64 === mySteamId ? 'own-player' : ''}>
              <td>
                <Link className="player-cell" to={`/players/${p.steam_id64}`}>
                  <Avatar small name={p.nickname} />
                  <span>
                    <strong>{p.nickname}</strong>
                    {p.steam_id64 === mySteamId && <small>Вы</small>}
                  </span>
                </Link>
              </td>
              <td>
                <span className={`team team-${p.team}`}>{p.team ?? '—'}</span>
              </td>
              {(
                [
                  'kills',
                  'deaths',
                  'assists',
                  'kd',
                  'adr',
                  'hs_percent',
                  'kr',
                  'rounds_played',
                ] as const
              ).map((key) => (
                <td
                  key={key}
                  title={p[key] == null ? p.missing_reasons.join('; ') || 'Нет данных' : undefined}
                  className={key === 'adr' || key === 'kd' ? 'metric-highlight' : ''}
                >
                  {p[key] == null
                    ? '—'
                    : fmt(
                        p[key],
                        key === 'kd' || key === 'kr'
                          ? 2
                          : key === 'adr' || key === 'hs_percent'
                            ? 1
                            : 0,
                      )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
