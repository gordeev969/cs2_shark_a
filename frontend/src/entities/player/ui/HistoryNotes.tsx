import type { Insights } from '@/shared/api/contracts'
import { ShieldCheck, TrendingUp } from 'lucide-react'

export function HistoryNotes({ insights }: { insights: Insights }) {
  return (
    <div className="insight-block">
      <div className="section-heading">
        <div>
          <h2>Наблюдения по истории</h2>
          <p>{insights.sample_size} матчей · собственная локальная выборка</p>
        </div>
        <ShieldCheck size={20} />
      </div>
      <div className="notice">
        <strong>
          {insights.status === 'insufficient'
            ? 'Сначала — достаточная выборка'
            : 'Сравнение с вашей историей'}
        </strong>
        <p>{insights.message}</p>
      </div>
      {insights.observations.map((o) => (
        <div className="observation" key={o.metric}>
          <TrendingUp size={18} />
          <p>{o.text}</p>
        </div>
      ))}
      <p className="muted tiny">
        {insights.source}. Сравнения с глобальной популяцией игроков нет.
      </p>
    </div>
  )
}
