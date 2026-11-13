export type Scoring = 'ppr' | 'half' | 'std'

export interface WeekRef {
  season: number
  week: number
  is_backtest: boolean
}

export interface PositionMetric {
  rows: number
  model_mae: number
  baseline_mae: number
}

export interface TeamInfo {
  name: string
  nickname: string
  color: string
  color2: string
  logo_url: string
}

export interface Summary {
  teams: Record<string, TeamInfo>
  season: number | null
  week: number | null
  weeks: WeekRef[]
  positions: string[]
  last_refreshed: string | null
  model: null | {
    trained_at: string
    trained_through: { season: number; week: number }
    training_rows: number
    training_seconds: number
    metrics: {
      holdout_season?: number
      rows?: number
      model_mae?: number
      baseline_mae?: number
      by_position?: Record<string, PositionMetric>
    }
    feature_importance: { feature: string; share: number }[]
  }
}

export interface PredictionRow {
  rank: number
  player_id: string
  name: string
  position: string
  team: string
  opponent: string
  is_home: boolean
  headshot_url: string
  projected: number
  recent_avg_ppr: number | null
  injury_status: string | null
  injury: string | null
  actual: number | null
  is_backtest: boolean
}

export interface PredictionsResponse {
  season: number | null
  week: number | null
  scoring: Scoring
  results: PredictionRow[]
}

export interface PlayerWeek {
  week: number
  opponent: string
  is_home: boolean | null
  actual: number | null
  projected: number | null
  is_backtest: boolean | null
  injury_status: string | null
  line: null | { pass: string; rush: string; rec: string; dst: string }
}

export interface PlayerDetail {
  player_id: string
  name: string
  position: string
  team: string
  headshot_url: string
  season: number
  scoring: Scoring
  games_played: number
  season_avg: number | null
  weeks: PlayerWeek[]
}

export interface AccuracyPick {
  week: number
  position: string
  name: string
  player_id: string
  team: string
  projected: number
  actual: number
  baseline: number | null
  live: boolean
}

export interface AccuracySummary {
  games: number
  mae: number
  within_5: number
  baseline_mae: number | null
  live_games: number
}

export interface Accuracy {
  season: number
  overall: AccuracySummary | null
  weeks: (AccuracySummary & { week: number })[]
  by_position: Record<string, AccuracySummary>
  best_calls: AccuracyPick[]
  biggest_misses: AccuracyPick[]
}

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const qs = query.toString()
  const res = await fetch(`/api/${path}${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json() as Promise<T>
}

export const api = {
  summary: () => get<Summary>('summary'),
  predictions: (params: { season?: number; week?: number; scoring: Scoring; position?: string; search?: string }) =>
    get<PredictionsResponse>('predictions', params),
  accuracy: () => get<Accuracy>('accuracy'),
  player: (id: string, scoring: Scoring) => get<PlayerDetail>(`players/${encodeURIComponent(id)}`, { scoring }),
}
