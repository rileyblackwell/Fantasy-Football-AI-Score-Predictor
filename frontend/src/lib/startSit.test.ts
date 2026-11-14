import { describe, expect, it } from 'vitest'
import type { PlayerWeek, PredictionRow } from './api'
import { confidenceFor, MAX_PICKS, parsePicks, recentGames, recommend, searchPlayers } from './startSit'

function row(id: string, name: string, projected: number, extra: Partial<PredictionRow> = {}): PredictionRow {
  return {
    rank: 0,
    player_id: id,
    name,
    position: 'WR',
    team: 'DET',
    opponent: 'NE',
    is_home: true,
    headshot_url: '',
    projected,
    recent_avg_ppr: null,
    injury_status: null,
    injury: null,
    bye_week: null,
    actual: null,
    is_backtest: false,
    ...extra,
  }
}

function game(week: number, actual: number | null): PlayerWeek {
  return { week, opponent: 'NE', is_home: true, actual, projected: 10, is_backtest: false, injury_status: null, line: null }
}

describe('parsePicks', () => {
  it('reads ids in order and drops blanks and repeats', () => {
    expect(parsePicks('a, b,,a,c')).toEqual(['a', 'b', 'c'])
  })

  it('caps the number of picks', () => {
    expect(parsePicks('a,b,c,d,e,f')).toHaveLength(MAX_PICKS)
  })

  it('handles a missing or repeated query value', () => {
    expect(parsePicks(undefined)).toEqual([])
    expect(parsePicks(['a', 'b'])).toEqual(['a', 'b'])
  })
})

describe('searchPlayers', () => {
  const rows = [
    row('1', 'Jared Goff', 16.7, { position: 'QB' }),
    row('2', 'Amon-Ra St. Brown', 19.6),
    row('3', 'Jameson Williams', 11.2),
    row('4', 'Josh Allen', 21.1, { team: 'BUF' }),
    row('5', 'Stefon Diggs', 5.0),
  ]

  it('returns nothing for an empty query', () => {
    expect(searchPlayers(rows, '  ')).toEqual([])
  })

  it('puts names that start with the query first, then best projection', () => {
    expect(searchPlayers(rows, 'st').map((r) => r.player_id)).toEqual(['5', '2'])
  })

  it('matches a team abbreviation and skips players already picked', () => {
    expect(searchPlayers(rows, 'det', ['2']).map((r) => r.player_id)).toEqual(['1', '3', '5'])
    expect(searchPlayers(rows, 'buf').map((r) => r.player_id)).toEqual(['4'])
  })
})

describe('recentGames', () => {
  it('takes the latest games played before the week, newest first', () => {
    const weeks = [game(1, 10), game(2, 20), game(3, null), game(4, 15), game(5, 30), game(6, null)]
    expect(recentGames(weeks, 6).map((w) => w.week)).toEqual([5, 4, 2])
    expect(recentGames(weeks, 3, 5).map((w) => w.week)).toEqual([2, 1])
  })
})

describe('recommend', () => {
  it('starts the highest projection and reports the margin', () => {
    const verdict = recommend([row('a', 'A', 12.4), row('b', 'B', 18.1), row('c', 'C', 14.0)])
    expect(verdict.start?.player_id).toBe('b')
    expect(verdict.margin).toBe(4.1)
    expect(verdict.confidence).toBe('clear')
    expect(verdict.sit.map((r) => r.player_id)).toEqual(['c', 'a'])
  })

  it('never starts a player who is ruled out', () => {
    const verdict = recommend([row('a', 'A', 20, { injury_status: 'Out' }), row('b', 'B', 9)])
    expect(verdict.start?.player_id).toBe('b')
    expect(verdict.margin).toBeNull()
    expect(verdict.out.map((r) => r.player_id)).toEqual(['a'])
    expect(verdict.sit.map((r) => r.player_id)).toEqual(['a'])
  })

  it('has no starter when everyone is out or nobody is picked', () => {
    expect(recommend([row('a', 'A', 20, { injury_status: 'Out' })]).start).toBeNull()
    expect(recommend([]).start).toBeNull()
  })

  it('calls close margins a lean or a toss-up', () => {
    expect(confidenceFor(0.6)).toBe('toss-up')
    expect(confidenceFor(1)).toBe('toss-up')
    expect(confidenceFor(2.5)).toBe('lean')
    expect(confidenceFor(3.1)).toBe('clear')
    expect(recommend([row('a', 'A', 15.2), row('b', 'B', 14.8)]).confidence).toBe('toss-up')
  })
})
