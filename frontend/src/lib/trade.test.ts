import { describe, expect, it } from 'vitest'
import { basisNote, judgeTrade, MAX_PER_SIDE, parseSide, type RosPlayer, searchPool, weekByWeek } from './trade'

function player(id: string, name: string, total: number, extra: Partial<RosPlayer> = {}): RosPlayer {
  return {
    player_id: id,
    name,
    position: 'WR',
    team: 'DET',
    headshot_url: '',
    injury_status: null,
    roster_status: 'ACT',
    basis: 'projection',
    per_game: 10,
    games_left: 5,
    bye_week: null,
    total,
    ...extra,
  }
}

describe('parseSide', () => {
  it('reads ids in order, drops blanks and repeats, and caps the side', () => {
    expect(parseSide('a, b,,a')).toEqual(['a', 'b'])
    expect(parseSide('a,b,c,d,e,f,g')).toHaveLength(MAX_PER_SIDE)
  })

  it('skips players already on the other side', () => {
    expect(parseSide('a,b,c', ['b'])).toEqual(['a', 'c'])
    expect(parseSide(undefined)).toEqual([])
  })
})

describe('searchPool', () => {
  const pool = [
    player('1', 'Jared Goff', 120, { position: 'QB' }),
    player('2', 'Amon-Ra St. Brown', 140),
    player('3', 'Josh Allen', 150, { team: 'BUF' }),
    player('4', 'Stefon Diggs', 40),
  ]

  it('puts names that start with the query first, then most points', () => {
    expect(searchPool(pool, 'st').map((p) => p.player_id)).toEqual(['4', '2'])
  })

  it('matches a team and skips excluded players', () => {
    expect(searchPool(pool, 'det', ['2']).map((p) => p.player_id)).toEqual(['1', '4'])
    expect(searchPool(pool, ' ')).toEqual([])
  })
})

describe('judgeTrade', () => {
  it('calls a big gain a clear win', () => {
    const v = judgeTrade([player('a', 'A', 100)], [player('b', 'B', 130)])
    expect(v).toEqual({ giveTotal: 100, getTotal: 130, net: 30, outcome: 'gain', lean: 'clear' })
  })

  it('calls a small gap even and a middling one a lean', () => {
    expect(judgeTrade([player('a', 'A', 100)], [player('b', 'B', 104)]).outcome).toBe('even')
    // 5% of 200 is 10 points, so a 9 point gap is still even.
    expect(judgeTrade([player('a', 'A', 200)], [player('b', 'B', 191)]).outcome).toBe('even')
    const lean = judgeTrade([player('a', 'A', 100)], [player('b', 'B', 90)])
    expect([lean.outcome, lean.lean, lean.net]).toEqual(['lose', 'lean', -10])
  })

  it('adds up multi-player sides', () => {
    const v = judgeTrade([player('a', 'A', 80.2), player('b', 'B', 40.1)], [player('c', 'C', 150)])
    expect([v.giveTotal, v.net, v.outcome]).toEqual([120.3, 29.7, 'gain'])
  })
})

describe('weekByWeek', () => {
  it('totals each week and lists players with no game', () => {
    const give = [
      player('a', 'A', 25, {
        games: [
          { week: 10, opponent: 'NE', is_home: true, points: 12 },
          { week: 12, opponent: 'GB', is_home: false, points: 13 },
        ],
      }),
    ]
    const get = [player('b', 'B', 30, { games: [10, 11, 12].map((week) => ({ week, opponent: 'NE', is_home: true, points: 10 })) })]
    expect(weekByWeek(give, get, 10, 12)).toEqual([
      { week: 10, give: 12, get: 10, giveIdle: [], getIdle: [] },
      { week: 11, give: 0, get: 10, giveIdle: ['A'], getIdle: [] },
      { week: 12, give: 13, get: 10, giveIdle: [], getIdle: [] },
    ])
  })
})

describe('basisNote', () => {
  it('explains anything other than a normal projection', () => {
    expect(basisNote(player('a', 'A', 1))).toBeNull()
    expect(basisNote(player('a', 'A', 0, { basis: 'inactive', roster_status: 'CUT' }))).toMatch(/active roster/)
    expect(basisNote(player('a', 'A', 0, { basis: 'inactive', roster_status: 'RES' }))).toMatch(/injured reserve/)
    expect(basisNote(player('a', 'A', 1, { injury_status: 'Out', basis: 'season_avg' }))).toMatch(/season average/)
    expect(basisNote(player('a', 'A', 1, { basis: 'recent_projection' }))).toMatch(/No game this week/)
  })
})
