import { get, type Scoring } from './api'

export const WAIVER_POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const

/** Projection rank at or above which a player is probably already rostered in a 12-team league. */
export const STARTER_RANK: Record<string, number> = { QB: 12, RB: 24, WR: 30, TE: 12 }

export interface ShareTrend {
  recent: number | null
  prior: number | null
  change: number | null
}

export interface WaiverRow {
  player_id: string
  name: string
  position: string
  team: string
  opponent: string | null
  is_home: boolean | null
  headshot_url: string
  /** Projection for the upcoming week, or null when the player has no game (bye) or no projection. */
  projected: number | null
  /** Rank by projection within the position this week. */
  position_rank: number | null
  /** When the player has no projection this week (e.g. on bye): the earlier week whose projection set the rank. */
  rank_from_week: number | null
  injury_status: string | null
  injury: string | null
  points_recent: number
  points_prior: number
  history: { week: number; snap_share: number | null; target_share: number | null }[]
  rising_snaps: boolean
  rising_targets: boolean
  trend_score: number
  snap_share: ShareTrend
  target_share: ShareTrend
  games_recent: number
  games_prior: number
}

export interface WaiversResponse {
  season: number | null
  week: number | null
  /** The latest week whose games are in the trend. */
  through_week: number | null
  scoring: Scoring
  results: WaiverRow[]
}

export function fetchWaivers(params: { season?: number; week?: number; scoring: Scoring }) {
  return get<WaiversResponse>('waivers', params)
}

/** True when the player's projection already ranks them as an every-week starter. */
export function isLikelyStarter(row: WaiverRow): boolean {
  const cutoff = STARTER_RANK[row.position]
  return row.position_rank !== null && cutoff !== undefined && row.position_rank <= cutoff
}

export interface WaiverFilters {
  position: string
  hideStarters: boolean
  hideOut: boolean
}

export function filterWaivers(rows: WaiverRow[], filters: WaiverFilters): WaiverRow[] {
  return rows.filter(
    (r) =>
      (filters.position === 'ALL' || r.position === filters.position) &&
      (!filters.hideStarters || !isLikelyStarter(r)) &&
      (!filters.hideOut || r.injury_status !== 'Out'),
  )
}

/** A share (0-1) as a whole percent, e.g. 0.853 -> "85%". */
export function pct(value: number | null): string {
  return value === null ? '–' : `${Math.round(value * 100)}%`
}

/** A share change as signed percentage points, e.g. 0.12 -> "+12 pts". */
export function pctChange(value: number | null): string {
  if (value === null) return '–'
  const rounded = Math.round(value * 100)
  return `${rounded > 0 ? '+' : ''}${rounded} pts`
}

/** One line on why a player was flagged, e.g. "Snaps 40% → 85%, targets 8% → 24%". */
export function whyFlagged(row: WaiverRow): string {
  const parts: string[] = []
  if (row.rising_snaps) parts.push(`Snaps ${pct(row.snap_share.prior)} → ${pct(row.snap_share.recent)}`)
  if (row.rising_targets) {
    const label = parts.length ? 'targets' : 'Target share'
    parts.push(`${label} ${pct(row.target_share.prior)} → ${pct(row.target_share.recent)}`)
  }
  return parts.join(', ')
}
