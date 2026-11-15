import { describe, expect, it } from 'vitest'
import { CONSISTENCY, consistencyInfo, rangeBar } from './consistency'

describe('consistencyInfo', () => {
  it('maps each label to its display text', () => {
    expect(consistencyInfo({ consistency: 'steady', floor: 9, ceiling: 30 })?.label).toBe('Steady')
    expect(consistencyInfo({ consistency: 'swingy', floor: 3, ceiling: 22 })?.label).toBe('Swingy')
    expect(consistencyInfo({ consistency: 'boom_bust', floor: 0, ceiling: 15 })?.label).toBe('Boom or bust')
  })

  it('shows nothing when the projection has no range', () => {
    expect(consistencyInfo({ consistency: null, floor: null, ceiling: null })).toBeNull()
    expect(consistencyInfo({})).toBeNull()
    expect(consistencyInfo({ consistency: 'steady', floor: null, ceiling: 20 })).toBeNull()
  })

  it('gives every label a blurb and an icon', () => {
    for (const info of Object.values(CONSISTENCY)) {
      expect(info.blurb.length).toBeGreaterThan(10)
      expect(info.icon).toMatch(/^M/)
    }
  })
})

describe('rangeBar', () => {
  it('places the band and the projection on a shared scale', () => {
    expect(rangeBar(5, 15, 25, 50)).toEqual({ left: 10, width: 40, marker: 30 })
  })

  it('stretches the scale when a ceiling runs past it', () => {
    expect(rangeBar(10, 20, 40, 20)).toEqual({ left: 25, width: 75, marker: 50 })
  })

  it('handles a zero floor and an all-zero range', () => {
    expect(rangeBar(0, 4, 12, 24).left).toBe(0)
    expect(rangeBar(0, 0, 0, 0)).toEqual({ left: 0, width: 0, marker: 0 })
  })
})
