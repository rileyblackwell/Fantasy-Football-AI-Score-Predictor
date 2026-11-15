import { describe, expect, it } from 'vitest'
import { grade, hitRate } from './grade'

describe('grade', () => {
  it('marks projections within 5 points as hits, either direction', () => {
    expect(grade(14.2, 17.0)).toBe('hit')
    expect(grade(14.2, 9.9)).toBe('hit')
    expect(grade(14.2, 14.2)).toBe('hit')
  })

  it('counts exactly 5 points as a hit, compared as shown', () => {
    expect(grade(15, 10)).toBe('hit')
    expect(grade(10.1, 15.1)).toBe('hit')
    expect(grade(15.04, 10)).toBe('hit') // shows as 15.0 vs 10.0
    expect(grade(15.1, 10)).toBe('miss')
  })

  it('marks bigger misses', () => {
    expect(grade(12, 25.3)).toBe('miss')
    expect(grade(18.5, 2)).toBe('miss')
    expect(grade(3, -2.1)).toBe('miss')
  })

  it('leaves unplayed or unprojected games ungraded', () => {
    expect(grade(12, null)).toBeNull()
    expect(grade(null, 12)).toBeNull()
  })
})

describe('hitRate', () => {
  it('counts hits over graded games only', () => {
    const rate = hitRate([
      { projected: 10, actual: 12 },
      { projected: 10, actual: 20 },
      { projected: 10, actual: 6 },
      { projected: 10, actual: null },
    ])
    expect(rate).toEqual({ hits: 2, graded: 3, share: 2 / 3 })
  })

  it('is null when nothing has been played', () => {
    expect(hitRate([])).toBeNull()
    expect(hitRate([{ projected: 10, actual: null }])).toBeNull()
  })
})
