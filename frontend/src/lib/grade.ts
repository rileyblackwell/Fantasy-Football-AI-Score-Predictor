/** A projection counts as a good call when the actual score lands within this many points of it. */
export const CLOSE_CALL_POINTS = 5

export type Grade = 'hit' | 'miss'

export interface Graded {
  projected: number | null
  actual: number | null
}

/**
 * Grade one projection against the real score: 'hit' within 5 points, 'miss' otherwise, and null when there is
 * nothing to grade yet (no projection, or the player hasn't played). Compared at one decimal, as the numbers are
 * shown, so a 15.0 projection and a 10.0 actual count as within 5.
 */
export function grade(projected: number | null, actual: number | null): Grade | null {
  if (projected === null || actual === null) return null
  const tenths = Math.abs(Math.round(actual * 10) - Math.round(projected * 10))
  return tenths <= CLOSE_CALL_POINTS * 10 ? 'hit' : 'miss'
}

/** How many graded projections were within 5 points, or null when nothing has been played yet. */
export function hitRate(rows: Graded[]): { hits: number; graded: number; share: number } | null {
  let hits = 0
  let graded = 0
  for (const row of rows) {
    const result = grade(row.projected, row.actual)
    if (result === null) continue
    graded += 1
    if (result === 'hit') hits += 1
  }
  return graded ? { hits, graded, share: hits / graded } : null
}
