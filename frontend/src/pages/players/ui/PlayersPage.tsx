import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useData } from '@/shared/api'
import { Title, Gate, Empty, Avatar } from '@/shared/ui'
import { Search, ChevronRight } from 'lucide-react'
import { useSettings } from '@/entities/settings'

export function PlayersPage() {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setSearch(query), 200)
    return () => clearTimeout(timer)
  }, [query])
  const result = useData<{ steam_id64: string; latest_nickname: string; matches: number }[]>(
    `/api/players?query=${encodeURIComponent(search)}`,
  )
  const { settings } = useSettings()
  return (
    <>
      <Title
        eyebrow="БИБЛИОТЕКА / ИГРОКИ"
        title="Знакомые по серверу"
        subtitle="Поиск только среди участников ваших импортов. Без внешней истории Steam."
      />
      <section className="panel">
        <div className="section-heading">
          <h2>Локальные профили</h2>
          <label className="search-field player-search">
            <Search size={16} />
            <input
              aria-label="Никнейм или SteamID64"
              placeholder="Никнейм или SteamID64"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
        <Gate {...result}>
          {result.data?.length ? (
            <div className="player-grid">
              {result.data.map((p) => (
                <Link className="player-card" key={p.steam_id64} to={`/players/${p.steam_id64}`}>
                  <Avatar name={p.latest_nickname} />
                  <div>
                    <strong>
                      {p.latest_nickname}
                      {settings?.steam_id64 === p.steam_id64 && <span className="you-tag">Вы</span>}
                    </strong>
                    <code>{p.steam_id64}</code>
                    <span>{p.matches} матчей в базе</span>
                  </div>
                  <ChevronRight size={16} />
                </Link>
              ))}
            </div>
          ) : (
            <Empty
              title={query ? 'Игрок не найден' : 'Профилей пока нет'}
              text={
                query
                  ? 'Попробуйте другой никнейм. Здесь доступны только игроки из импортированных матчей.'
                  : 'Загрузите первую демку, чтобы увидеть всех её участников.'
              }
            />
          )}
        </Gate>
      </section>
    </>
  )
}
