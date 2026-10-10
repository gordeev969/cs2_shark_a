import { Link } from 'react-router-dom'
import { ArrowRight, Crosshair, Swords, Users, ChevronRight } from 'lucide-react'
import type { Match, Profile, SteamUser } from '@/shared/api/contracts'
import { Avatar } from '@/shared/ui'
import { fmt } from '@/shared/lib'
import { isSnapshotMode } from '@/shared/config'
import { mapName, Status } from '@/entities/match'

export function DashboardOverview({
  profile,
  latestMatch,
  user,
}: {
  profile: Profile | null
  latestMatch?: Match
  user: SteamUser | null
}) {
  const nickname = user?.display_name ?? profile?.latest_nickname
  return (
    <div className="overview-grid">
      <section className="profile-overview">
        <div className="overview-profile-heading">
          <span className="overview-kicker">
            {isSnapshotMode ? 'Выбранный игрок' : 'Ваш профиль'}
          </span>
          {profile && (
            <Link to={`/players/${profile.steam_id64}`} className="text-link">
              Профиль игрока <ArrowRight size={16} />
            </Link>
          )}
        </div>
        <div className="overview-identity">
          {user?.avatar_url ? (
            <img
              className="steam-avatar"
              src={user.avatar_url}
              alt=""
              referrerPolicy="no-referrer"
            />
          ) : (
            <Avatar name={nickname ?? 'CS'} />
          )}
          <div>
            <h2>{nickname ?? 'Начните с первого матча'}</h2>
            <span>
              {profile
                ? `Матчей в наблюдаемой истории: ${profile.summary.matches}`
                : 'Настоящие демки. Проверяемая статистика.'}
            </span>
          </div>
        </div>
        {profile ? (
          <>
            <div
              className="overview-kda"
              aria-label="Убийства, смерти и ассисты за наблюдаемую историю"
            >
              <div>
                <strong>{fmt(profile.summary.kills, 0)}</strong>
                <span>Убийства</span>
              </div>
              <div>
                <strong>{fmt(profile.summary.deaths, 0)}</strong>
                <span>Смерти</span>
              </div>
              <div>
                <strong>{fmt(profile.summary.assists, 0)}</strong>
                <span>Ассисты</span>
              </div>
            </div>
            <div className="overview-footnote">
              <Crosshair size={13} /> Только завершённые раунды · без данных разминки
            </div>
          </>
        ) : (
          <div className="overview-start">
            <p>Разберите запись, чтобы увидеть показатели игрока и каждого раунда.</p>
            <Link className="button secondary" to={user ? '/connect' : '/import'}>
              {user ? 'Подключить CS2' : 'Загрузить демку'} <ArrowRight size={16} />
            </Link>
          </div>
        )}
      </section>
      {latestMatch ? (
        <Link className="latest-match-card" to={`/matches/${latestMatch.id}`}>
          <div className="latest-match-heading">
            <span className="overview-kicker">Последний матч</span>
            {latestMatch.result ? (
              <span className={`match-result ${latestMatch.result}`}>
                {latestMatch.result === 'win'
                  ? 'Победа'
                  : latestMatch.result === 'loss'
                    ? 'Поражение'
                    : 'Ничья'}
              </span>
            ) : (
              <Status value={latestMatch.status} />
            )}
          </div>
          <div className="latest-match-core">
            <div>
              <span className="map-category">Запись #{latestMatch.id}</span>
              <h2>{mapName(latestMatch.map_name)}</h2>
            </div>
            <strong className="latest-score">
              {latestMatch.team_scores ? (
                <>
                  {latestMatch.team_scores.A}
                  <span>:</span>
                  {latestMatch.team_scores.B}
                </>
              ) : (
                '—'
              )}
            </strong>
          </div>
          <div className="latest-match-meta">
            <span>
              <Swords size={14} />
              {latestMatch.round_count} завершённых раундов
            </span>
            <span>
              <Users size={14} />
              {latestMatch.player_count} игроков
            </span>
          </div>
          <div className="latest-match-footer">
            Открыть отчёт матча <ChevronRight size={17} />
          </div>
        </Link>
      ) : (
        <section className="latest-match-card no-match">
          <Crosshair size={38} />
          <h2>Ваш первый матч</h2>
          <p>Здесь появится карта, результат и переход к подробному отчёту.</p>
        </section>
      )}
    </div>
  )
}
