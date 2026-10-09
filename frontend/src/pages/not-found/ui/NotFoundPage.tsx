import { Link } from 'react-router-dom'
import { Empty } from '@/shared/ui'

export function NotFoundPage() {
  return (
    <Empty
      title="Страница не найдена"
      text="Перейдите в обзор или библиотеку матчей."
      action={
        <Link className="button primary" to="/">
          В обзор
        </Link>
      }
    />
  )
}
