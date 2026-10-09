import { Link } from 'react-router-dom'
import { Crosshair, ChevronRight, FileUp } from 'lucide-react'
import type { Match } from '@/shared/api/contracts'
import { Empty } from '@/shared/ui'
import { date, fmt } from '@/shared/lib'
import { mapName } from '../lib/map-name'
import { Status } from './Status'

export function MatchRows({ matches }: { matches: Match[] }) {
  if (!matches.length)
    return (
      <Empty
        title="Здесь будут ваши матчи"
        text="Загрузите первую CS2-демку. Мы сохраним участников, раунды и статистику в локальной базе."
        action={
          <Link className="button primary" to="/import">
            <FileUp size={16} /> Загрузить демку
          </Link>
        }
      />
    )
  return (
    <div className="match-list">
      {matches.map((m) => (
        <Link key={m.id} to={`/matches/${m.id}`} className="match-row">
          <div className="map-tile">
            <Crosshair size={23} />
          </div>
          <div className="match-main">
            <strong>{mapName(m.map_name)}</strong>
            <span>
              {m.played_at ? 'Матч' : 'Импорт'} #{m.id} · {date(m.played_at ?? m.imported_at)}
            </span>
          </div>
          <div className="match-meta">
            {m.personal_stats ? (
              <>
                <span>
                  {fmt(m.personal_stats.kills, 0)} / {fmt(m.personal_stats.deaths, 0)} /{' '}
                  {fmt(m.personal_stats.assists, 0)} <small>K / D / A</small>
                </span>
                <span>
                  ADR {fmt(m.personal_stats.adr, 1)} · HS {fmt(m.personal_stats.hs_percent, 0)}%
                </span>
              </>
            ) : (
              <>
                <span>{m.player_count} игроков</span>
                <span>{m.round_count} завершённых раундов</span>
              </>
            )}
          </div>
          <div className="score">
            {m.team_scores ? (
              `${m.team_scores.A} : ${m.team_scores.B}`
            ) : (
              <span className="muted tiny">счёт: нет данных</span>
            )}
          </div>
          {m.status === 'ready' && m.result ? (
            <span className={`match-result ${m.result}`}>
              {m.result === 'win' ? 'Победа' : m.result === 'loss' ? 'Поражение' : 'Ничья'}
            </span>
          ) : (
            <Status value={m.status} />
          )}
          <ChevronRight className="muted" size={17} />
        </Link>
      ))}
    </div>
  )
}
