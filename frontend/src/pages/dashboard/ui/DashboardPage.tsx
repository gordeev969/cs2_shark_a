import { isSnapshotMode } from '@/shared/config'
import { Link } from 'react-router-dom'
import { useData } from '@/shared/api'
import type { Dashboard } from '@/shared/api/contracts'
import { Title, Gate, Empty, GlowLink } from '@/shared/ui'
import { FileUp, ArrowRight, TrendingUp, Activity } from 'lucide-react'
import { useAuth } from '@/entities/auth'
import { SyncMatches } from '@/features/connect-cs2'
import { connectionStatus, isSyncPending } from '@/entities/cs2-connection'
import { useSettings } from '@/entities/settings'
import { MatchRows, hasPendingImports } from '@/entities/match'
import { StatCards } from '@/widgets/player-stats'
import { Trend } from '@/widgets/player-history'
import { DashboardOverview } from '@/widgets/dashboard-overview'
import { DashboardSkeleton } from './DashboardSkeleton'

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
        title="Обзор игры"
        subtitle={
          isSnapshotMode
            ? 'Разбор настоящей демки. Все важные показатели в одном месте.'
            : 'Ваши матчи и показатели. От результата к каждому раунду.'
        }
        action={
          isSnapshotMode ? (
            <GlowLink to={d?.recent_matches[0] ? `/matches/${d.recent_matches[0].id}` : '/matches'}>
              Открыть отчёт матча <ArrowRight size={17} />
            </GlowLink>
          ) : d?.cs2?.connected ? (
            <SyncMatches pending={isSyncPending(d.cs2)} onQueued={result.retry} />
          ) : (
            <GlowLink to={user ? '/connect' : '/import'}>
              <FileUp size={17} /> {user ? 'Подключить CS2' : 'Загрузить демку'}
            </GlowLink>
          )
        }
      />
      <Gate {...result} loadingContent={<DashboardSkeleton />}>
        {d && (
          <>
            {!!d.queued_count && (
              <p className="notice" role="status">
                Ваших демок в обработке: {d.queued_count}. Общая очередь разбирает записи по одной.{' '}
                Готовая статистика доступна сразу.{' '}
                <Link className="text-link" to="/matches">
                  Открыть очередь <ArrowRight size={14} />
                </Link>
              </p>
            )}
            {d.cs2?.error && (
              <p className="notice" role="status">
                {d.cs2.error}{' '}
                <Link className="text-link" to="/connect">
                  Настройки подключения →
                </Link>
              </p>
            )}
            {user && (
              <div className="account-connection">
                <span>
                  <span className="live-dot" /> Steam-профиль подтверждён
                </span>
                <Link className="text-link" to="/connect">
                  {d.cs2?.connected
                    ? `CS2: ${connectionStatus(d.cs2.status)}`
                    : 'Подключить историю CS2'}{' '}
                  <ArrowRight size={14} />
                </Link>
              </div>
            )}
            <DashboardOverview profile={d.personal} latestMatch={d.recent_matches[0]} user={user} />
            <StatCards
              variant="strip"
              matches={d.match_count}
              players={d.player_count}
              summary={d.personal?.rolling}
            />
            <div className="dashboard-grid">
              <section className="panel recent-panel">
                <div className="section-heading">
                  <div>
                    <h2>Последние матчи</h2>
                    <p>
                      Матчей: {d.match_count} · Игроков: {d.player_count}
                    </p>
                  </div>
                  <Link className="text-link" to="/matches">
                    Все матчи <ArrowRight size={14} />
                  </Link>
                </div>
                <MatchRows matches={d.recent_matches} />
              </section>
              <section className="panel personal-panel">
                <div className="section-heading">
                  <h2>Что говорит история</h2>
                  <TrendingUp size={19} />
                </div>
                {d.personal ? (
                  <>
                    <div className="history-status">
                      <span className="history-icon">
                        <Activity size={21} />
                      </span>
                      <div>
                        <strong>
                          {d.personal.insights.status === 'insufficient'
                            ? 'Собираем историю'
                            : 'Есть что сравнить'}
                        </strong>
                        <span>
                          {d.personal.insights.status === 'insufficient'
                            ? `${d.personal.insights.sample_size} из ${d.personal.insights.minimum_matches} матчей для анализа изменений`
                            : `${d.personal.insights.sample_size} матчей в наблюдаемой истории`}
                        </span>
                      </div>
                    </div>
                    <div
                      className="sample-track"
                      role="progressbar"
                      aria-label="Матчи для анализа изменений"
                      aria-valuemin={0}
                      aria-valuemax={d.personal.insights.minimum_matches}
                      aria-valuenow={Math.min(
                        d.personal.insights.sample_size,
                        d.personal.insights.minimum_matches,
                      )}
                      aria-valuetext={`${d.personal.insights.sample_size} матчей в истории; минимум ${d.personal.insights.minimum_matches} для анализа`}
                    >
                      {Array.from({ length: d.personal.insights.minimum_matches }, (_, i) => (
                        <span
                          key={i}
                          className={i < d.personal!.insights.sample_size ? 'filled' : ''}
                        />
                      ))}
                    </div>
                    <p className="history-explanation">{d.personal.insights.message}</p>
                    <Link className="text-link" to={`/players/${d.personal.steam_id64}`}>
                      Подробная история игрока <ArrowRight size={15} />
                    </Link>
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
