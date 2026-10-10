import type { Summary } from '@/shared/api/contracts'
import { fmt } from '@/shared/lib'
import { Swords, Target, Activity, TrendingUp, Crosshair } from 'lucide-react'

export function StatCards({
  summary,
  matches,
  players,
  variant = 'cards',
}: {
  summary?: Summary
  matches?: number
  players?: number
  variant?: 'cards' | 'strip'
}) {
  const items =
    matches != null
      ? [
          {
            label: 'K/D',
            value: fmt(summary?.kd, 2),
            hint: 'Отношение убийств к смертям',
            icon: Target,
          },
          {
            label: 'ADR',
            value: fmt(summary?.adr, 1),
            hint: 'Эффективный урон за раунд',
            icon: Activity,
          },
          {
            label: 'Попадания в голову',
            value: summary?.hs_percent == null ? 'нет данных' : `${fmt(summary.hs_percent, 1)}%`,
            hint: 'Доля убийств в голову',
            icon: Crosshair,
          },
          {
            label: 'Убийства за раунд',
            value: fmt(summary?.kr, 2),
            hint: summary
              ? `${fmt(summary.rounds_played, 0)} завершённых раундов`
              : `${players ?? 0} игроков в базе`,
            icon: TrendingUp,
          },
        ]
      : [
          {
            label: 'Наблюдаемых матчей',
            value: fmt(summary?.matches, 0),
            hint: 'Матчи в наблюдаемой истории',
            icon: Swords,
          },
          {
            label: 'K/D',
            value: fmt(summary?.kd, 2),
            hint: `${fmt(summary?.kills, 0)} K · ${fmt(summary?.deaths, 0)} D`,
            icon: Target,
          },
          {
            label: 'ADR',
            value: fmt(summary?.adr, 1),
            hint: `${summary?.adr_matches ?? 0} матчей с данными урона`,
            icon: Activity,
          },
          {
            label: 'Убийства / раунд',
            value: fmt(summary?.kr, 2),
            hint: `${fmt(summary?.rounds_played, 0)} сыгранных раундов`,
            icon: TrendingUp,
          },
        ]
  return (
    <div className={`stat-grid ${variant === 'strip' ? 'stat-grid-strip' : ''}`.trim()}>
      {items.map((item) => (
        <div
          key={item.label}
          className={`stat-card ${item.label === 'ADR' ? 'featured-stat' : ''}`}
        >
          <div className="stat-label">
            {item.label}
            <item.icon size={17} />
          </div>
          <strong className={item.value === 'нет данных' ? 'missing' : ''}>{item.value}</strong>
          <span>{item.hint}</span>
        </div>
      ))}
    </div>
  )
}
