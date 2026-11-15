import { describe, expect, it } from 'vitest'
import { filterWaivers, isLikelyStarter, pct, pctChange, whyFlagged, type WaiverRow } from './waivers'

function row(id: string, extra: Partial<WaiverRow> = {}): WaiverRow {
  return {
    player_id: id,
    name: id,
    position: 'WR',
    team: 'DET',
    opponent: 'NE',
    is_home: true,
    headshot_url: '',
    projected: 9.5,
    position_rank: 50,
    injury_status: null,
    injury: null,
    points_recent: 12,
    points_prior: 6,
    history: [],
    rising_snaps: true,
    rising_targets: true,
    trend_score: 0.5,
    snap_share: { recent: 0.85, prior: 0.4, change: 0.45 },
    target_share: { recent: 0.24, prior: 0.08, change: 0.16 },
    games_recent: 3,
    games_prior: 4,
    ...extra,
  }
}

describe('isLikelyStarter', () => {
  it('uses a cutoff per position', () => {
    expect(isLikelyStarter(row('a', { position: 'WR', position_rank: 30 }))).toBe(true)
    expect(isLikelyStarter(row('b', { position: 'WR', position_rank: 31 }))).toBe(false)
    expect(isLikelyStarter(row('c', { position: 'TE', position_rank: 13 }))).toBe(false)
    expect(isLikelyStarter(row('d', { position: 'QB', position_rank: 3 }))).toBe(true)
  })

  it('treats a player with no projection as available', () => {
    expect(isLikelyStarter(row('a', { position_rank: null }))).toBe(false)
  })
})

describe('filterWaivers', () => {
  const rows = [
    row('starter', { position_rank: 5 }),
    row('out', { injury_status: 'Out' }),
    row('rb', { position: 'RB' }),
    row('wr'),
  ]

  it('hides starters and players ruled out', () => {
    const ids = filterWaivers(rows, { position: 'ALL', hideStarters: true, hideOut: true }).map((r) => r.player_id)
    expect(ids).toEqual(['rb', 'wr'])
  })

  it('keeps everyone when the toggles are off', () => {
    expect(filterWaivers(rows, { position: 'ALL', hideStarters: false, hideOut: false })).toHaveLength(4)
  })

  it('filters by position', () => {
    const ids = filterWaivers(rows, { position: 'RB', hideStarters: true, hideOut: true }).map((r) => r.player_id)
    expect(ids).toEqual(['rb'])
  })
})

describe('formatting', () => {
  it('shows shares and changes as percents', () => {
    expect(pct(0.853)).toBe('85%')
    expect(pct(null)).toBe('–')
    expect(pctChange(0.12)).toBe('+12 pts')
    expect(pctChange(-0.03)).toBe('-3 pts')
    expect(pctChange(null)).toBe('–')
  })

  it('explains why a player was flagged', () => {
    expect(whyFlagged(row('a'))).toBe('Snaps 40% → 85%, targets 8% → 24%')
    expect(whyFlagged(row('b', { rising_snaps: false }))).toBe('Target share 8% → 24%')
    expect(whyFlagged(row('c', { rising_targets: false }))).toBe('Snaps 40% → 85%')
  })
})
