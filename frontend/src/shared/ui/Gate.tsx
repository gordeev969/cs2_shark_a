import type { ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'

export function Gate({
  loading,
  error,
  retry,
  children,
}: {
  loading: boolean
  error?: string
  retry: () => void
  children: ReactNode
}) {
  if (loading)
    return (
      <div className="loading" role="status">
        <LoaderCircle className="spin" /> Загружаем локальные данные…
      </div>
    )
  if (error)
    return (
      <div className="error-box" role="alert">
        <strong>Не удалось загрузить данные</strong>
        <p>{error}</p>
        <button className="button secondary" onClick={retry}>
          Повторить
        </button>
      </div>
    )
  return children
}
