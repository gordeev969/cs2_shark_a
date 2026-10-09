import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { snapshotRequest } from '../src/shared/api/snapshot'
import type { Dashboard, MatchDetail, Profile, Settings } from '../src/shared/api/contracts'

const exported = JSON.parse(
  readFileSync(new URL('../public/snapshot.json', import.meta.url), 'utf8'),
)
const selected = exported.settings.steam_id64 as string
const preferences = new Map<string, string>()
beforeEach(() => {
  preferences.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => preferences.get(key) ?? null,
    setItem: (key: string, value: string) => preferences.set(key, value),
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => exported })),
  )
})
describe('public backend export', () => {
  it('preserves real metrics, null dates and match totals', async () => {
    const match = await snapshotRequest<MatchDetail>('/api/matches/1')
    expect(match.players).toHaveLength(10)
    expect(match.rounds).toHaveLength(9)
    expect(match.players.reduce((sum, p) => sum + (p.kills ?? 0), 0)).toBe(64)
    expect(match.players.reduce((sum, p) => sum + (p.deaths ?? 0), 0)).toBe(64)
    expect(match.played_at).toBeNull()
    const profile = await snapshotRequest<Profile>(`/api/players/${selected}`)
    expect(profile.summary).toEqual(exported.profiles[selected].summary)
    expect(profile.insights.status).toBe('insufficient')
  })
  it('changes only browser selection and uses that player’s precomputed dashboard', async () => {
    const other = Object.keys(exported.profiles).find((id) => id !== selected)!
    await snapshotRequest('/api/settings', {
      method: 'PUT',
      body: JSON.stringify({ steam_id64: other, compact: true }),
    })
    const settings = await snapshotRequest<Settings>('/api/settings')
    const dashboard = await snapshotRequest<Dashboard>('/api/dashboard')
    expect(settings.compact).toBe(true)
    expect(dashboard.personal?.steam_id64).toBe(other)
    expect(dashboard.recent_matches[0].personal_stats?.steam_id64).toBe(other)
    expect(dashboard.personal?.summary).toEqual(exported.profiles[other].summary)
  })
  it('rejects uploads, authentication, unknown players and aborted reads', async () => {
    await expect(snapshotRequest('/api/matches/import', { method: 'POST' })).rejects.toThrow(
      'недоступно',
    )
    await expect(snapshotRequest('/api/auth/session')).rejects.toThrow('отсутствуют')
    await expect(
      snapshotRequest('/api/settings', {
        method: 'PUT',
        body: JSON.stringify({ steam_id64: '76561198000000000' }),
      }),
    ).rejects.toThrow('участника')
    const controller = new AbortController()
    controller.abort()
    await expect(snapshotRequest('/api/health', { signal: controller.signal })).rejects.toThrow()
  })
})
