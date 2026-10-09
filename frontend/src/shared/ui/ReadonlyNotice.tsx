import { Link } from 'react-router-dom'
import { sourceRepository } from '@/shared/config'
export function ReadonlyNotice() {
  return (
    <section className="panel">
      <span className="tag subtle">GITHUB PAGES / ПРОСМОТР</span>
      <h2>Для своих матчей нужна полная версия</h2>
      <p className="muted">
        На этом сайте опубликован отчёт настоящей контрольной демки. Вход через Steam, подключение
        CS2 и разбор новых файлов работают в серверной версии приложения.
      </p>
      <p>
        <Link className="button primary" to="/matches">
          Открыть разобранный матч
        </Link>
      </p>
      <a className="text-link" href={`${sourceRepository}#запуск`} target="_blank" rel="noreferrer">
        Исходники и инструкции запуска →
      </a>
    </section>
  )
}
