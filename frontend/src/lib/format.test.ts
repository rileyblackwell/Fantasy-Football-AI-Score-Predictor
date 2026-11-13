import { describe, expect, it } from 'vitest'
import { featureLabel, injuryClass, injuryShort, matchup, relativeTime } from './format'

describe('format helpers', () => {
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
