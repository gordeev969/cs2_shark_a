export type Value = number | null
export interface Metrics {
  kills: Value
  deaths: Value
  assists: Value
  kd: Value
  adr: Value
  hs_percent: Value
  kr: Value
  rounds_played: Value
  effective_damage?: Value
  hs_kills?: Value
}
export interface Participant extends Metrics {
  steam_id64: string
  nickname: string
  team: string | null
  missing_reasons: string[]
}
export interface Match {
  personal_stats?: Participant | null
  result?: 'win' | 'loss' | 'draw' | null
  id: number
  status: 'queued' | 'processing' | 'ready' | 'failed'
  map_name: string | null
  imported_at: string
  played_at: string | null
  team_scores: { A: number; B: number } | null
  error: string | null
  player_count: number
  round_count: number
  parser_version: string | null
  diagnostics: string[]
}
export interface Round {
  number: number
  winning_side: number
  start_tick: number
  end_tick: number
  players: Record<
    string,
    { side: number; kills: Value; deaths: Value; assists: Value; effective_damage: Value }
  >
}
export interface MatchDetail extends Match {
  players: Participant[]
  rounds: Round[]
}
export interface Summary extends Metrics {
  matches: number
  adr_matches: number
  adr_rounds: number
}
export interface History extends Participant {
  match_id: number
  map_name: string | null
  imported_at: string
}
export interface Observation {
  metric: string
  current: number
  baseline: number
  delta: number
  current_matches: number
  baseline_matches: number
  text: string
}
export interface Insights {
  status: string
  message: string
  source: string
  sample_size: number
  minimum_matches: number
  observations: Observation[]
}
export interface Profile {
  steam_id64: string
  latest_nickname: string
  summary: Summary
  rolling: Summary
  history: History[]
  insights: Insights
  map_splits: (Summary & { map_name: string })[]
}
export interface Settings {
  steam_id64: string
  compact: boolean
  ai_enabled: boolean
}
export interface Dashboard {
  profile?: SteamUser | null
  cs2?: CS2Connection | null
  queued_count?: number
  match_count: number
  player_count: number
  recent_matches: Match[]
  personal: Profile | null
  settings: Settings
}
export interface Health {
  status: string
  max_upload_bytes: number
  parser_version: string
  retain_demos: boolean
  ai_enabled: boolean
}

export interface SteamUser {
  steam_id64: string
  display_name: string
  avatar_url: string | null
  profile_url: string
}
export interface AuthSession {
  authenticated: boolean
  required: boolean
  user: SteamUser | null
  csrf_token: string | null
}
export interface CS2Connection {
  connected: boolean
  status: string
  error: string | null
  last_sync: string | null
  initial_sharecode: string | null
  latest_sharecode: string | null
  discovered_count: number
  imported_count: number
  pending_count: number
  failed_count: number
  gc_configured: boolean
  steam_api_configured: boolean
}
