import type { Scoring } from './api'

/** The most players on one side of a trade. */
export const MAX_PER_SIDE = 5

export interface RosGame {
  week: number
  opponent: string
  is_home: boolean
  points: number
}

/** How a player's per-game rate was set; see backend/predictor/rest_of_season.py. */
export type RosBasis = 'projection' | 'recent_projection' | 'season_avg' | 'inactive' | 'none'

export interface RosPlayer {
  player_id: string
  name: string
  position: string
  team: string
  headshot_url: string
  injury_status: string | null
  /** nflverse roster status, such as ACT (active) or RES (injured reserve). */
  roster_status: string
  basis: RosBasis
  per_game: number
  games_left: number
  /** The team's bye week if it falls in the remaining window, else null. */
  bye_week: number | null
  total: number
  /** Week-by-week points; only present when the players were asked for by id. */
  games?: RosGame[]
}

export interface RosResponse {
  season: number | null
  from_week: number | null
  through_week: number | null
  last_week: number | null
  scoring: Scoring
  players: RosPlayer[]
}

export async function fetchRestOfSeason(params: { scoring: Scoring; through?: number; ids?: string[] }): Promise<RosResponse> {
  const query = new URLSearchParams({ scoring: params.scoring })
  if (params.through) query.set('through', String(params.through))
  if (params.ids) query.set('ids', params.ids.join(','))
  const res = await fetch(`/api/rest-of-season?${query}`)
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json() as Promise<RosResponse>
}

/** Player ids for one side from a `?give=` / `?get=` query value, without blanks, repeats or ids in `taken`. */
export function parseSide(value: unknown, taken: string[] = []): string[] {
  const raw = Array.isArray(value) ? value.join(',') : typeof value === 'string' ? value : ''
  const ids: string[] = []
  for (const id of raw.split(',').map((part) => part.trim())) {
    if (id && !ids.includes(id) && !taken.includes(id)) ids.push(id)
    if (ids.length === MAX_PER_SIDE) break
  }
  return ids
}

/** Players for the picker: name or team matches, most rest-of-season points first, skipping `exclude`. */
export function searchPool(pool: RosPlayer[], query: string, exclude: string[] = [], limit = 8): RosPlayer[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return pool
    .filter((p) => !exclude.includes(p.player_id))
    .filter((p) => p.name.toLowerCase().includes(q) || p.team.toLowerCase() === q)
    .sort((a, b) => {
      const starts = Number(b.name.toLowerCase().startsWith(q)) - Number(a.name.toLowerCase().startsWith(q))
      return starts || b.total - a.total
    })
    .slice(0, limit)
}

export type TradeLean = 'even' | 'lean' | 'clear'

export interface TradeVerdict {
  giveTotal: number
  getTotal: number
  /** Rest-of-season points you gain (negative when you lose points). */
  net: number
  /** 'gain' when your side comes out ahead, 'lose' when it falls behind, 'even' when it's close. */
  outcome: 'gain' | 'lose' | 'even'
  lean: TradeLean
}

/** A gap at or under this many points, or this share of the bigger side, reads as even. */
export const EVEN_POINTS = 5
export const EVEN_SHARE = 0.05
/** A gap at or under this share of the bigger side is a lean rather than a clear win. */
export const LEAN_SHARE = 0.15

const round1 = (n: number) => Math.round(n * 10) / 10

export function sumPoints(players: RosPlayer[]): number {
  return round1(players.reduce((sum, p) => sum + p.total, 0))
}

export function judgeTrade(give: RosPlayer[], get: RosPlayer[]): TradeVerdict {
  const giveTotal = sumPoints(give)
  const getTotal = sumPoints(get)
  const net = round1(getTotal - giveTotal)
  const bigger = Math.max(giveTotal, getTotal)
  const gap = Math.abs(net)
  let lean: TradeLean = 'clear'
  if (gap <= Math.max(EVEN_POINTS, bigger * EVEN_SHARE)) lean = 'even'
  else if (gap <= bigger * LEAN_SHARE) lean = 'lean'
  const outcome = lean === 'even' ? 'even' : net > 0 ? 'gain' : 'lose'
  return { giveTotal, getTotal, net, outcome, lean }
}

export interface WeekRow {
  week: number
  give: number
  get: number
  /** Players on each side with no game that week (bye or schedule gap). */
  giveIdle: string[]
  getIdle: string[]
}

/** Each remaining week's points for both sides, so bye-week holes show up. */
export function weekByWeek(give: RosPlayer[], get: RosPlayer[], fromWeek: number, throughWeek: number): WeekRow[] {
  const rows: WeekRow[] = []
  const side = (players: RosPlayer[], week: number) => {
    let points = 0
    const idle: string[] = []
    for (const p of players) {
      const game = p.games?.find((g) => g.week === week)
      if (game) points += game.points
      else idle.push(p.name)
    }
    return { points: round1(points), idle }
  }
  for (let week = fromWeek; week <= throughWeek; week++) {
    const g = side(give, week)
    const r = side(get, week)
    rows.push({ week, give: g.points, get: r.points, giveIdle: g.idle, getIdle: r.idle })
  }
  return rows
}

/** A short note on where a player's rest-of-season number comes from, or null for the normal case. */
export function basisNote(p: RosPlayer): string | null {
  if (p.basis === 'inactive') {
    return p.roster_status === 'RES'
      ? 'On injured reserve with no return date, so no points are counted.'
      : 'Not on an active roster, so no points are counted.'
  }
  if (p.basis === 'none') return 'No projection or games this season yet.'
  if (p.injury_status === 'Out') {
    return p.basis === 'season_avg'
      ? 'Out this week; later weeks use their season average.'
      : 'Out this week; later weeks use their projection from an earlier week.'
  }
  if (p.basis === 'recent_projection') return 'No game this week; uses their most recent projection.'
  if (p.basis === 'season_avg') return 'No projection yet; uses their season average.'
  return null
}
