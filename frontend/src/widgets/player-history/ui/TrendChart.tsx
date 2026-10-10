import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fmt } from '@/shared/lib'

export default function TrendChart({
  data,
  metric,
}: {
  data: { label: string; value: number | null }[]
  metric: 'adr' | 'kd'
}) {
  return (
    <ResponsiveContainer width="100%" height={235}>
      <LineChart data={data}>
        <CartesianGrid stroke="var(--line)" strokeDasharray="3 5" vertical={false} />
        <XAxis dataKey="label" stroke="var(--muted)" tickLine={false} axisLine={false} />
        <YAxis stroke="var(--muted)" tickLine={false} axisLine={false} width={42} />
        <Tooltip
          contentStyle={{
            background: '#21132f',
            border: '1px solid #664a80',
            borderRadius: 10,
          }}
          formatter={(v) => [fmt(Number(v), 2), metric === 'adr' ? 'ADR' : 'K/D']}
        />
        <Line
          dataKey="value"
          stroke="var(--accent)"
          strokeWidth={2.5}
          dot={{ r: 3, fill: 'var(--accent)' }}
          connectNulls={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
