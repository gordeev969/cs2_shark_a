import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Profile } from '@/shared/api/contracts'
import { fmt } from '@/shared/lib'
import { Activity } from 'lucide-react'

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
          <ResponsiveContainer width="100%" height={235}>
            <LineChart data={data}>
              <CartesianGrid stroke="#252e30" strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="label" stroke="#7e8c8c" tickLine={false} axisLine={false} />
              <YAxis stroke="#7e8c8c" tickLine={false} axisLine={false} width={42} />
              <Tooltip
                contentStyle={{
                  background: '#172022',
                  border: '1px solid #35423d',
                  borderRadius: 10,
                }}
                formatter={(v) => [fmt(Number(v), 2), metric === 'adr' ? 'ADR' : 'K/D']}
              />
              <Line
                dataKey="value"
                stroke="#c0f36b"
                strokeWidth={2.5}
                dot={{ r: 3, fill: '#c0f36b' }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}
