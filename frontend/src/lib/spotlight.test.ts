import { describe, expect, it } from 'vitest'
import type { PredictionRow } from './api'
import { topThree } from './spotlight'

function row(id: string, projected: number, actual: number | null): PredictionRow {
  return {
    rank: 0,
    player_id: id,
    name: id,
    position: 'WR',
    team: 'DET',
    opponent: 'MIA',
    is_home: true,
    headshot_url: '',
    projected,
    recent_avg_ppr: null,
    injury_status: null,
    injury: null,
    actual,
    is_backtest: true,
  }
}

const rows = [row('a', 20, 5), row('b', 18, 30), row('c', 15, null), row('d', 10, 25), row('e', 9, 12)]

describe('topThree', () => {
  it('picks the top three projections for the upcoming week', () => {
    expect(topThree(rows, false).map((r) => r.player_id)).toEqual(['a', 'b', 'c'])
  })

  it('picks the top three actual scorers for a past week and skips players with no score', () => {
    expect(topThree(rows, true).map((r) => r.player_id)).toEqual(['b', 'd', 'e'])
  })

  it('does not reorder the rows it was given', () => {
    const before = rows.map((r) => r.player_id)
    topThree(rows, true)
    topThree(rows, false)
    expect(rows.map((r) => r.player_id)).toEqual(before)
  })
})
