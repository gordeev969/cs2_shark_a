import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useData } from '@/shared/api'
import type { Match } from '@/shared/api/contracts'
import { Title, Gate, Empty } from '@/shared/ui'
import { FileUp, Search } from 'lucide-react'
import { MatchRows, hasPendingMatches } from '@/entities/match'

export function MatchesPage() {
  const result = useData<Match[]>('/api/matches', hasPendingMatches)
  const [filter, setFilter] = useState('')
  const matches =
    result.data?.filter(
      (m) => !filter || (m.map_name ?? '').toLowerCase().includes(filter.toLowerCase()),
    ) ?? []
  return (
    <>
      <Title
        eyebrow="БИБЛИОТЕКА / МАТЧИ"
        title="История матчей"
        subtitle="Каждая запись — из вашей демки. Даты ниже обозначают время импорта."
        action={
          <Link to="/import" className="button primary">
            <FileUp size={16} /> Новый импорт
          </Link>
        }
      />
      <section className="panel">
        <div className="section-heading">
          <h2>
            Локальная библиотека <span className="count">{result.data?.length ?? 0}</span>
          </h2>
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label="Поиск карты"
              placeholder="Поиск по карте"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
        </div>
        <Gate {...result}>
          {filter && !matches.length ? (
            <Empty title="Карта не найдена" text="Попробуйте другое название карты." />
          ) : (
            <MatchRows matches={matches} />
          )}
        </Gate>
      </section>
    </>
  )
}
