import { describe, expect, it } from 'vitest'
import { featureLabel, injuryClass, injuryShort, matchup, points, relativeTime, signedPoints } from './format'

describe('format helpers', () => {
  it('never shows negative zero', () => {
    expect(points(-0.04)).toBe('0.0')
    expect(points(-0)).toBe('0.0')
    expect(points(-1.25)).toBe('-1.3')
    expect(points(12.345, 2)).toBe('12.35')
    expect(signedPoints(-0.02)).toBe('0.0')
    expect(signedPoints(3.21)).toBe('+3.2')
    expect(signedPoints(-3.21)).toBe('-3.2')
  })

  it('formats home and away matchups', () => {
    expect(matchup('DAL', true)).toBe('vs DAL')
    expect(matchup('DAL', false)).toBe('@ DAL')
    expect(matchup('DAL', null)).toBe('DAL')
  })

  it('maps injury statuses to badges', () => {
    expect(injuryShort('Questionable')).toBe('Q')
    expect(injuryShort('Doubtful')).toBe('D')
    expect(injuryShort('Out')).toBe('OUT')
    expect(injuryClass('Out')).toBe('inj-out')
    expect(injuryClass(null)).toBe('')
  })

  it('labels model features in plain words and falls back to the raw name', () => {
    expect(featureLabel('implied_team_total')).toBe('Vegas implied team total')
    expect(featureLabel('something_new')).toBe('something_new')
  })

  it('describes how long ago something happened', () => {
    const now = new Date('2026-11-13T12:00:00Z')
    expect(relativeTime(null, now)).toBe('never')
    expect(relativeTime('2026-11-13T11:59:45Z', now)).toBe('just now')
    expect(relativeTime('2026-11-13T11:30:00Z', now)).toBe('30 min ago')
    expect(relativeTime('2026-11-13T07:00:00Z', now)).toBe('5 hr ago')
    expect(relativeTime('2026-11-12T12:00:00Z', now)).toBe('1 day ago')
  })
})
