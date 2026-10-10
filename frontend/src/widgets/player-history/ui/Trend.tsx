import { lazy, Suspense, useState } from 'react'
import type { Profile } from '@/shared/api/contracts'
import { Activity } from 'lucide-react'

const TrendChart = lazy(() => import('./TrendChart'))

export function Trend({ profile }: { profile: Profile }) {
  const [metric, setMetric] = useState<'adr' | 'kd'>('adr')
  const data = profile.history
    .slice(0, 20)
    .reverse()
    .map((h) => ({ label: `#${h.match_id}`, value: h[metric] }))
  return (
    <section
      className={`panel trend-panel ${data.length < 2 || data.every((d) => d.value == null) ? 'trend-insufficient' : ''}`}
    >
      <div className="section-heading">
        <div>
          <h2>Динамика игры</h2>
          <p>До 20 матчей; дата игры, иначе время импорта</p>
        </div>
        <div className="segmented">
          {(['adr', 'kd'] as const).map((m) => (
            <button
              key={m}
              aria-pressed={m === metric}
              className={metric === m ? 'active' : ''}
              onClick={() => setMetric(m)}
            >
              {m === 'adr' ? 'ADR' : 'K/D'}
            </button>
          ))}
        </div>
      </div>
      {data.length < 2 || data.every((d) => d.value == null) ? (
        <div className="chart-empty">
          <Activity size={28} />
          <p>
            Для графика нужны минимум два матча
            <br />с доступным показателем {metric === 'adr' ? 'ADR' : 'K/D'}.
          </p>
        </div>
      ) : (
        <div className="chart">
          <Suspense
            fallback={
              <div className="chart-skeleton" role="status" aria-label="Загружаем график" />
            }
          >
            <TrendChart data={data} metric={metric} />
          </Suspense>
        </div>
      )}
    </section>
  )
}
