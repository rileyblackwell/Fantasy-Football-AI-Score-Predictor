import type { PredictionRow } from './api'

/**
 * The three players shown in the cards above the table.
 *
 * For the upcoming week (the one the model is predicting) that is the top three
 * projections. For a past week it is the top three actual scorers, so the cards
 * show who really led the week; players with no actual score are left out.
 */
export function topThree(rows: PredictionRow[], byActual: boolean): PredictionRow[] {
  if (byActual) {
    return rows
      .filter((r) => r.actual !== null)
      .sort((a, b) => (b.actual as number) - (a.actual as number) || b.projected - a.projected)
      .slice(0, 3)
  }
  return [...rows].sort((a, b) => b.projected - a.projected).slice(0, 3)
}
