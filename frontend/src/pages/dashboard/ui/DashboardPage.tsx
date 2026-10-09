import { isSnapshotMode } from '@/shared/config'
import { Link } from 'react-router-dom'
import { useData } from '@/shared/api'
import type { Dashboard } from '@/shared/api/contracts'
import { Title, Gate, Empty, Avatar } from '@/shared/ui'
import { FileUp, ArrowRight, Crosshair, TrendingUp, ChevronRight } from 'lucide-react'
import { useAuth } from '@/entities/auth'
import { SyncMatches } from '@/features/connect-cs2'
import { connectionStatus, isSyncPending } from '@/entities/cs2-connection'
import { useSettings } from '@/entities/settings'
import { MatchRows, hasPendingImports } from '@/entities/match'
import { HistoryNotes } from '@/entities/player'
import { StatCards } from '@/widgets/player-stats'
import { Trend } from '@/widgets/player-history'

export function DashboardPage() {
  const { user } = useAuth()
  const { settings } = useSettings()
  const result = useData<Dashboard>(
    `/api/dashboard?steam_id64=${settings?.steam_id64 ?? ''}`,
    hasPendingImports,
  )
  const d = result.data
  return (
    <>
      <Title
        eyebrow={isSnapshotMode ? 'КОНТРОЛЬНАЯ ДЕМКА / ОБЗОР' : 'ЛИЧНОЕ ПРОСТРАНСТВО / ОБЗОР'}
        title={isSnapshotMode ? 'Матч. В деталях.' : 'Ваша игра. В деталях.'}
        subtitle="Разбирайте матчи, замечайте изменения и играйте осознаннее."
        action={
          isSnapshotMode ? (
            <Link className="button primary" to="/matches">
              Открыть отчёт матча <ArrowRight size={17} />
            </Link>
          ) : d?.cs2?.connected ? (
            <SyncMatches pending={isSyncPending(d.cs2)} onQueued={result.retry} />
          ) : (
            <Link className="button primary" to={user ? '/connect' : '/import'}>
              <FileUp size={17} /> {user ? 'Подключить CS2' : 'Загрузить демку'}
            </Link>
          )
        }
      />
      <Gate {...result}>
        {d && (
          <>
            {user && (
              <section className="panel account-banner">
                <Link to={`/players/${user.steam_id64}`} className="profile-inline">
                  {user.avatar_url ? (
                    <img
                      className="steam-avatar"
                      src={user.avatar_url}
                      alt=""
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <Avatar name={user.display_name} />
                  )}
                  <div>
                    <strong>{user.display_name}</strong>
                    <span>
                      Ваш Steam-профиль · {d.personal?.summary.matches ?? 0} разобранных матчей
                    </span>
                  </div>
                  <ChevronRight size={20} />
                </Link>
                <Link className="text-link" to="/connect">
                  {d.cs2?.connected
                    ? `CS2: ${connectionStatus(d.cs2.status)}`
                    : 'Подключить историю CS2 →'}
                </Link>
              </section>
            )}
            {d.cs2?.error && (
              <p className="notice" role="status">
                {d.cs2.error}{' '}
                <Link className="text-link" to="/connect">
                  Настройки подключения →
                </Link>
              </p>
            )}
            <div className="hero-panel">
              <div className="hero-content">
                <span className="tag">
                  <span className="live-dot" />{' '}
                  {isSnapshotMode ? 'ФАКТЫ ИЗ НАСТОЯЩЕЙ ДЕМКИ' : 'ЛОКАЛЬНАЯ АНАЛИТИКА CS2'}
                </span>
                <h2>
                  Каждый раунд
                  <br />
                  рассказывает больше.
                </h2>
                <p>
                  {isSnapshotMode ? (
                    'Mirage. 10 игроков. Каждый показатель рассчитан по событиям настоящей записи матча.'
                  ) : (
                    <>
                      Убийства, эффективный урон и ваша история —<br className="desktop" /> из
                      настоящих демо, на вашем компьютере.
                    </>
                  )}
                </p>
                <Link
                  to={
                    isSnapshotMode ? '/matches' : user && !d.cs2?.connected ? '/connect' : '/import'
                  }
                  className="hero-link"
                >
                  {isSnapshotMode
                    ? 'Открыть статистику матча'
                    : user && !d.cs2?.connected
                      ? 'Подключить свою историю'
                      : 'Разобрать демку вручную'}{' '}
                  <ArrowRight size={18} />
                </Link>
              </div>
              <div className="hero-radar" aria-hidden="true">
                <div className="radar-circle one" />
                <div className="radar-circle two" />
                <div className="radar-circle three" />
                <Crosshair size={86} strokeWidth={0.8} />
                <span className="radar-dot a" />
                <span className="radar-dot b" />
                <span className="radar-dot c" />
                <span className="radar-label">REPLAY → INSIGHT</span>
              </div>
              <span className="hero-index">01 / PREMIER ANALYZER</span>
            </div>
            <StatCards
              matches={d.match_count}
              players={d.player_count}
              summary={d.personal?.rolling}
            />
            <div className="dashboard-grid">
              <section className="panel recent-panel">
                <div className="section-heading">
                  <div>
                    <h2>Последние матчи</h2>
                    <p>Результат, K / D / A и ADR из разобранных демок</p>
                  </div>
                  <Link className="text-link" to="/matches">
                    Все матчи <ArrowRight size={14} />
                  </Link>
                </div>
                <MatchRows matches={d.recent_matches} />
              </section>
              <section className="panel personal-panel">
                <div className="section-heading">
                  <h2>{isSnapshotMode ? 'Выбранный игрок' : 'Ваш прогресс'}</h2>
                  <TrendingUp size={19} />
                </div>
                {d.personal ? (
                  <>
                    <Link className="profile-inline" to={`/players/${d.personal.steam_id64}`}>
                      <Avatar name={d.personal.latest_nickname} />
                      <div>
                        <strong>{d.personal.latest_nickname}</strong>
                        <span>{d.personal.summary.matches} матчей в базе</span>
                      </div>
                      <ChevronRight size={17} />
                    </Link>
                    <HistoryNotes insights={d.personal.insights} />
                  </>
                ) : (
                  <Empty
                    title={
                      settings?.steam_id64 ? 'Ваших матчей пока нет' : 'Выберите своего игрока'
                    }
                    text={
                      settings?.steam_id64
                        ? 'Импортируйте демку, в которой присутствует ваш SteamID64.'
                        : 'Укажите SteamID64 в настройках или выберите себя на странице игрока.'
                    }
                    action={
                      <Link to="/settings" className="button secondary">
                        Настроить профиль <ArrowRight size={15} />
                      </Link>
                    }
                  />
                )}
              </section>
            </div>
            {d.personal && <Trend profile={d.personal} />}
          </>
        )}
      </Gate>
    </>
  )
}
