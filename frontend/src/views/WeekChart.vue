<script setup lang="ts">
import { computed } from 'vue'
import type { PlayerWeek } from '../lib/api'

const props = defineProps<{ weeks: PlayerWeek[] }>()

const W = 640
const H = 220
const PAD = { top: 12, right: 12, bottom: 28, left: 34 }

const maxY = computed(() => {
  const values = props.weeks.flatMap((w) => [w.actual ?? 0, w.projected ?? 0])
  return Math.max(10, Math.ceil(Math.max(...values, 0) / 5) * 5)
})

const slot = computed(() => (W - PAD.left - PAD.right) / Math.max(props.weeks.length, 1))
const x = (i: number) => PAD.left + slot.value * i + slot.value / 2
const y = (v: number) => PAD.top + (H - PAD.top - PAD.bottom) * (1 - v / maxY.value)

const ticks = computed(() => {
  const step = maxY.value > 30 ? 10 : 5
  return Array.from({ length: Math.floor(maxY.value / step) + 1 }, (_, i) => i * step)
})

const projectedPath = computed(() =>
  props.weeks
    .map((w, i) => (w.projected === null ? null : `${x(i).toFixed(1)},${y(w.projected).toFixed(1)}`))
    .filter(Boolean)
    .join(' '),
)
</script>

<template>
  <div class="chart">
    <svg :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="Weekly actual fantasy points as bars, projections as a line">
      <g v-for="t in ticks" :key="t">
        <line :x1="PAD.left" :x2="W - PAD.right" :y1="y(t)" :y2="y(t)" class="grid" />
        <text :x="PAD.left - 6" :y="y(t) + 4" class="axis" text-anchor="end">{{ t }}</text>
      </g>
      <g v-for="(w, i) in weeks" :key="w.week">
        <rect
          v-if="w.actual !== null"
          :x="x(i) - slot * 0.3"
          :width="slot * 0.6"
          :y="y(w.actual)"
          :height="Math.max(0, y(0) - y(w.actual))"
          rx="3"
          class="bar"
        >
          <title>Week {{ w.week }}: {{ w.actual }} actual, {{ w.projected ?? '–' }} projected</title>
        </rect>
        <text :x="x(i)" :y="H - 8" class="axis" text-anchor="middle">{{ w.week }}</text>
      </g>
      <polyline v-if="projectedPath" :points="projectedPath" class="proj-line" />
      <g v-for="(w, i) in weeks" :key="`p${w.week}`">
        <circle v-if="w.projected !== null" :cx="x(i)" :cy="y(w.projected)" r="4" class="proj-dot" :class="{ upcoming: w.actual === null }">
          <title>Week {{ w.week }} projection: {{ w.projected }}</title>
        </circle>
      </g>
    </svg>
    <div class="legend">
      <span><i class="sw bar-sw" /> Actual</span>
      <span><i class="sw line-sw" /> Projected</span>
      <span class="muted">Hollow dot = upcoming game</span>
    </div>
  </div>
</template>

<style scoped>
svg {
  width: 100%;
  height: auto;
  display: block;
}
.grid {
  stroke: var(--border);
  stroke-width: 1;
}
.axis {
  fill: var(--muted);
  font-size: 11px;
}
.bar {
  fill: var(--actual);
  opacity: 0.85;
}
.proj-line {
  fill: none;
  stroke: var(--accent);
  stroke-width: 2;
}
.proj-dot {
  fill: var(--accent);
  stroke: var(--surface);
  stroke-width: 2;
}
.proj-dot.upcoming {
  fill: var(--surface);
  stroke: var(--accent);
}
.legend {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 13px;
  margin-top: 8px;
}
.sw {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  vertical-align: -1px;
  margin-right: 4px;
}
.bar-sw {
  background: var(--actual);
}
.line-sw {
  background: var(--accent);
  height: 3px;
  vertical-align: 3px;
}
</style>
