import { isSnapshotMode } from '@/shared/config'
import type { Summary } from '@/shared/api/contracts'
import { fmt } from '@/shared/lib'
import { Swords, Users, Target, Activity, TrendingUp } from 'lucide-react'

export function StatCards({
  summary,
  matches,
  players,
}: {
  summary?: Summary
  matches?: number
  players?: number
}) {
  const items =
    matches != null
      ? [
          {
            label: 'Матчей в базе',
            value: fmt(matches, 0),
            hint: 'Успешно разобранные демки',
            icon: Swords,
          },
          {
            label: 'Игроков',
            value: fmt(players, 0),
            hint: isSnapshotMode ? 'Участники контрольной демки' : 'Из ваших локальных импортов',
            icon: Users,
          },
          {
            label: isSnapshotMode ? 'K/D выбранного игрока' : 'Личный K/D',
            value: fmt(summary?.kd, 2),
            hint: summary ? `Последние ${summary.matches} импортов` : 'Укажите свой SteamID64',
            icon: Target,
          },
          {
            label: isSnapshotMode ? 'ADR выбранного игрока' : 'Личный ADR',
            value: fmt(summary?.adr, 1),
            hint: summary
              ? `${summary.adr_matches} матчей с данными урона`
              : 'Укажите свой SteamID64',
            icon: Activity,
          },
        ]
      : [
          {
            label: 'Наблюдаемых матчей',
            value: fmt(summary?.matches, 0),
            hint: isSnapshotMode ? 'Опубликованная выборка' : 'Только ваша локальная база',
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
    <div className="stat-grid">
      {items.map((item) => (
        <div key={item.label} className="stat-card">
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
