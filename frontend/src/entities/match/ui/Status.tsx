import type { Match } from '@/shared/api/contracts'
import { CheckCircle2, X, LoaderCircle } from 'lucide-react'

export function Status({ value }: { value: Match['status'] }) {
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
      ) : (
        <LoaderCircle size={12} className="spin" />
      )}
      {labels[value]}
    </span>
  )
}
