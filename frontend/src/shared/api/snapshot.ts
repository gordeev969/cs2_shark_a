import type { Dashboard, Health, MatchDetail, Profile, Settings } from './contracts'

interface Snapshot {
  schema_version: number
  settings: Settings
  health: Health
  players: { steam_id64: string; latest_nickname: string; matches: number }[]
  profiles: Record<string, Profile>
  matches: Record<string, MatchDetail>
  dashboards: Record<string, Dashboard>
  insights: Record<string, { steam_id64: string; notes: unknown; history: unknown }[]>
}
const preferenceKey = 'cs2-public-viewer-settings-v1'
let snapshot: Promise<Snapshot> | undefined
async function loadSnapshot() {
  snapshot ??= fetch(`${import.meta.env.BASE_URL}snapshot.json`, { credentials: 'omit' })
    .then(async (response) => {
      if (!response.ok) throw new Error('Не удалось загрузить опубликованную статистику.')
      const data = (await response.json()) as Snapshot
      if (data.schema_version !== 1 || !data.dashboards || !data.profiles)
        throw new Error('Формат опубликованной статистики не поддерживается.')
      return data
    })
    .catch((error: unknown) => {
      snapshot = undefined
      throw error
    })
  return snapshot
}
function preferences(data: Snapshot): Settings {
  try {
    const saved = JSON.parse(localStorage.getItem(preferenceKey) ?? 'null') as Settings | null
    if (saved && (saved.steam_id64 === '' || data.profiles[saved.steam_id64]))
      return { steam_id64: saved.steam_id64, compact: !!saved.compact, ai_enabled: false }
  } catch {
    // Storage can be unavailable; the published default remains usable.
  }
  return { ...data.settings }
}
/** Reads a backend-calculated public export. It performs no game calculations. */
export async function snapshotRequest<T>(url: string, options?: RequestInit): Promise<T> {
  options?.signal?.throwIfAborted()
  const data = await loadSnapshot()
  options?.signal?.throwIfAborted()
  const route = new URL(url, 'https://viewer.invalid')
  const method = options?.method?.toUpperCase() ?? 'GET'
  const settings = preferences(data)
  let result: unknown
  if (route.pathname === '/api/settings' && method === 'PUT') {
    const input = JSON.parse(String(options?.body ?? '{}')) as Settings
    if (
      typeof input.steam_id64 !== 'string' ||
      (input.steam_id64 && !data.profiles[input.steam_id64])
    )
      throw new Error('Выберите участника опубликованного матча на странице игрока.')
    result = { steam_id64: input.steam_id64, compact: !!input.compact, ai_enabled: false }
    try {
      localStorage.setItem(preferenceKey, JSON.stringify(result))
    } catch {
      throw new Error('Браузер запретил сохранение настроек. Разрешите локальное хранилище.')
    }
  } else {
    if (method !== 'GET') throw new Error('В режиме просмотра изменение данных недоступно.')
    const steam = route.searchParams.get('steam_id64') || settings.steam_id64
    if (route.pathname === '/api/settings') result = settings
    else if (route.pathname === '/api/health') result = data.health
    else if (route.pathname === '/api/dashboard') {
      const dashboard = data.dashboards[steam] ?? data.dashboards['']
      result = { ...dashboard, settings }
    } else if (route.pathname === '/api/matches')
      result = (data.dashboards[settings.steam_id64] ?? data.dashboards['']).recent_matches
    else if (route.pathname === '/api/players') {
      const query = (route.searchParams.get('query') ?? '').toLocaleLowerCase()
      result = data.players.filter((p) =>
        `${p.latest_nickname} ${p.steam_id64}`.toLocaleLowerCase().includes(query),
      )
    } else {
      const player = /^\/api\/players\/(\d+)$/.exec(route.pathname)
      const match = /^\/api\/matches\/(\d+)(\/insights)?$/.exec(route.pathname)
      if (player) result = data.profiles[player[1]]
      if (match) {
        result = match[2]
          ? data.insights[match[1]]?.filter(
              (p) =>
                !route.searchParams.get('steam_id64') ||
                p.steam_id64 === route.searchParams.get('steam_id64'),
            )
          : data.matches[match[1]]
      }
    }
  }
  if (result === undefined) throw new Error('Данные отсутствуют в опубликованной выборке.')
  return structuredClone(result) as T
}
