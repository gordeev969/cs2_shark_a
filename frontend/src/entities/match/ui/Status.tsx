import type { Match } from '@/shared/api/contracts'
import { CheckCircle2, X, LoaderCircle, Clock3 } from 'lucide-react'

export function Status({ value, position }: { value: Match['status']; position?: number | null }) {
  const labels = {
    queued: 'В очереди',
    processing: 'Разбираем демку',
    ready: 'Готово',
    failed: 'Ошибка разбора',
  }
  return (
    <span className={`status ${value}`}>
      {value === 'ready' ? (
        <CheckCircle2 size={12} />
      ) : value === 'failed' ? (
        <X size={12} />
      ) : value === 'queued' ? (
        <Clock3 size={12} />
      ) : (
        <LoaderCircle size={12} className="spin" />
      )}
      {labels[value]}
      {value === 'queued' && position != null && ` · №${position}`}
    </span>
  )
}
