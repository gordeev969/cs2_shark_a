import type { Dashboard, Match } from '@/shared/api/contracts'
export const isMatchPending = (data: Pick<Match, 'status'>) =>
  data.status === 'queued' || data.status === 'processing'
export const hasPendingMatches = (data: Match[]) => data.some(isMatchPending)
export const hasPendingImports = (data: Dashboard) =>
  hasPendingMatches(data.recent_matches) ||
  !!data.queued_count ||
  !!(data.cs2 && ['queued', 'syncing'].includes(data.cs2.status))
