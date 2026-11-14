import type { PlayerWeek, PredictionRow } from './api'

/** The most players the Start/Sit page compares at once. */
export const MAX_PICKS = 4

/**
 * Player ids from the `?p=` query value ("id1,id2"), in order, without blanks or
 * repeats, and capped at MAX_PICKS.
 */
export function parsePicks(value: unknown): string[] {
  const raw = Array.isArray(value) ? value.join(',') : typeof value === 'string' ? value : ''
  const picks: string[] = []
  for (const id of raw.split(',').map((part) => part.trim())) {
    if (id && !picks.includes(id)) picks.push(id)
    if (picks.length === MAX_PICKS) break
  }
  return picks
}

/** Players for the picker: name or team matches, best projection first, skipping ones already picked. */
export function searchPlayers(rows: PredictionRow[], query: string, exclude: string[] = [], limit = 8): PredictionRow[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return rows
    .filter((r) => !exclude.includes(r.player_id))
    .filter((r) => r.name.toLowerCase().includes(q) || r.team.toLowerCase() === q)
    .sort((a, b) => {
      // Names that start with the query come before names that only contain it.
      const starts = Number(b.name.toLowerCase().startsWith(q)) - Number(a.name.toLowerCase().startsWith(q))
      return starts || b.projected - a.projected
    })
    .slice(0, limit)
}

/** Up to `count` most recent games played before `week`, newest first. */
export function recentGames(weeks: PlayerWeek[], week: number, count = 3): PlayerWeek[] {
  return weeks
    .filter((w) => w.week < week && w.actual !== null)
    .sort((a, b) => b.week - a.week)
    .slice(0, count)
}

export type Confidence = 'clear' | 'lean' | 'toss-up'

export interface Verdict {
  /** The player to start, or null when nobody picked is playing. */
  start: PredictionRow | null
  /** Points the starter is projected ahead of the next best option, or null with only one option. */
  margin: number | null
  confidence: Confidence
  /** Everyone else, best projection first. */
  sit: PredictionRow[]
  /** Picked players who are ruled out this week. */
  out: PredictionRow[]
}

/** Margins at or under these many points read as a toss-up or a lean. */
export const TOSS_UP_POINTS = 1
export const LEAN_POINTS = 3

export function confidenceFor(margin: number | null): Confidence {
  if (margin === null) return 'clear'
  if (margin <= TOSS_UP_POINTS) return 'toss-up'
  if (margin <= LEAN_POINTS) return 'lean'
  return 'clear'
}

/**
 * Who to start among the picked players: the highest projection among players
 * who are not ruled out. Players listed as Out always sit.
 */
export function recommend(rows: PredictionRow[]): Verdict {
  const out = rows.filter((r) => r.injury_status === 'Out')
  const available = rows.filter((r) => r.injury_status !== 'Out').sort((a, b) => b.projected - a.projected)
  const [start = null, ...rest] = available
  const margin = start && rest.length ? Math.round((start.projected - rest[0].projected) * 10) / 10 : null
  return { start, margin, confidence: confidenceFor(margin), sit: [...rest, ...out], out }
}
