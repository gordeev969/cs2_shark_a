import { api } from '@/shared/api'
import type { Settings } from '@/shared/api/contracts'
export const saveSettings = (steam_id64: string, compact: boolean) =>
  api<Settings>('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ steam_id64, compact }),
  })
