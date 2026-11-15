import type { PredictionRow } from './api'

export type Consistency = NonNullable<PredictionRow['consistency']>

export interface ConsistencyInfo {
  label: string
  /** One line on what the label means for a lineup decision. */
  blurb: string
  /** Tailwind classes for the pill (kept clear of the injury badge colors). */
  tone: string
  /** SVG path (24x24 viewBox) for the pill's icon: flat, wavy or zigzag. */
  icon: string
}

export const CONSISTENCY: Record<Consistency, ConsistencyInfo> = {
  steady: {
    label: 'Steady',
    blurb: 'Steadier than most. A bad week still usually scores something useful.',
    tone: 'bg-accent-soft text-accent',
    icon: 'M3 12h18',
  },
  swingy: {
    label: 'Swingy',
    blurb: 'Can land well above or well below the projection.',
    tone: 'bg-surface-3 text-fg',
    icon: 'M3 12c2.25-4 4.5-4 6.75 0s4.5 4 6.75 0 3.75-4 4.5-2',
  },
  boom_bust: {
    label: 'Boom or bust',
    blurb: 'Often scores little, with the odd big game.',
    tone: 'bg-(--pos-dst)/15 text-(--pos-dst)',
    icon: 'M3 15l4-8 4 12 4-14 4 10 2-4',
  },
}

/** The label for a projection, or null when it has no range (older weeks). */
export function consistencyInfo(row: Pick<PredictionRow, 'consistency' | 'floor' | 'ceiling'>): ConsistencyInfo | null {
  if (!row.consistency || row.floor == null || row.ceiling == null) return null
  return CONSISTENCY[row.consistency] ?? null
}

export interface RangeBar {
  /** Left edge and width of the range band, and where the projection sits, as % of the shared scale. */
  left: number
  width: number
  marker: number
}

/**
 * Where to draw a player's range on a scale from 0 to `scaleMax` points, so cards
 * side by side share one axis and can be compared at a glance.
 */
export function rangeBar(floor: number, projected: number, ceiling: number, scaleMax: number): RangeBar {
  const max = Math.max(scaleMax, ceiling, 1)
  const pct = (v: number) => Math.round((Math.min(Math.max(v, 0), max) / max) * 1000) / 10
  const left = pct(floor)
  return { left, width: Math.round((pct(ceiling) - left) * 10) / 10, marker: pct(projected) }
}
