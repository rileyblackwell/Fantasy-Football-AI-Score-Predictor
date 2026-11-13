<script setup lang="ts">
import { computed } from 'vue'
import type { PlayerWeek } from '../lib/api'

const props = defineProps<{ weeks: PlayerWeek[] }>()

const W = 720
const H = 240
const PAD = { top: 14, right: 12, bottom: 30, left: 36 }

const minY = computed(() => Math.min(0, ...props.weeks.map((w) => Math.min(w.actual ?? 0, w.projected ?? 0))))
const maxY = computed(() => {
  const values = props.weeks.flatMap((w) => [w.actual ?? 0, w.projected ?? 0])
  return Math.max(10, Math.ceil(Math.max(...values, 0) / 5) * 5)
})

const slot = computed(() => (W - PAD.left - PAD.right) / Math.max(props.weeks.length, 1))
const x = (i: number) => PAD.left + slot.value * i + slot.value / 2
const y = (v: number) => PAD.top + (H - PAD.top - PAD.bottom) * (1 - (v - minY.value) / (maxY.value - minY.value))
const barW = computed(() => Math.min(34, slot.value * 0.62))

const ticks = computed(() => {
  const step = maxY.value > 30 ? 10 : 5
  const out: number[] = []
  for (let t = Math.ceil(minY.value / step) * step; t <= maxY.value; t += step) out.push(t)
  return out
})
</script>

<template>
  <div class="chart">
    <svg :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="Weekly fantasy points: bars are actual scores, markers are projections">
      <g v-for="t in ticks" :key="t">
        <line :x1="PAD.left" :x2="W - PAD.right" :y1="y(t)" :y2="y(t)" class="grid" :class="{ zero: t === 0 }" />
        <text :x="PAD.left - 8" :y="y(t) + 4" class="axis" text-anchor="end">{{ t }}</text>
      </g>
      <g v-for="(w, i) in weeks" :key="w.week">
        <rect
          v-if="w.actual !== null"
          :x="x(i) - barW / 2"
          :width="barW"
          :y="Math.min(y(w.actual), y(0))"
          :height="Math.max(1, Math.abs(y(0) - y(w.actual)))"
          rx="4"
          class="bar"
          :class="{ beat: w.projected !== null && w.actual >= w.projected }"
        >
          <title>Week {{ w.week }}: {{ w.actual }} actual{{ w.projected !== null ? `, ${w.projected} projected` : '' }}</title>
        </rect>
        <rect
          v-if="w.projected !== null && w.actual === null"
          :x="x(i) - barW / 2"
          :width="barW"
          :y="y(w.projected)"
          :height="Math.max(1, y(0) - y(w.projected))"
          rx="4"
          class="bar upcoming"
        >
          <title>Week {{ w.week }} projection: {{ w.projected }}</title>
        </rect>
        <line
          v-if="w.projected !== null"
          :x1="x(i) - barW / 2 - 4"
          :x2="x(i) + barW / 2 + 4"
          :y1="y(w.projected)"
          :y2="y(w.projected)"
          class="proj-tick"
        />
        <text :x="x(i)" :y="H - 10" class="axis" text-anchor="middle">{{ w.week }}</text>
      </g>
    </svg>
    <div class="legend">
      <span><i class="sw sw-beat" /> Beat projection</span>
      <span><i class="sw sw-miss" /> Fell short</span>
      <span><i class="sw sw-tick" /> Projection</span>
      <span><i class="sw sw-up" /> Upcoming</span>
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
.grid.zero {
  stroke: var(--muted);
  stroke-opacity: 0.5;
}
.axis {
  fill: var(--muted);
  font-size: 11px;
  font-family: var(--font-body);
}
.bar {
  fill: var(--muted);
  fill-opacity: 0.45;
}
.bar.beat {
  fill: var(--accent);
  fill-opacity: 0.85;
}
.bar.upcoming {
  fill: none;
  stroke: var(--accent);
  stroke-width: 1.5;
  stroke-dasharray: 4 3;
}
.proj-tick {
  stroke: var(--text);
  stroke-width: 2.5;
  stroke-linecap: round;
}
.legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--muted);
  margin-top: 10px;
}
.sw {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
  vertical-align: -1px;
  margin-right: 5px;
}
.sw-beat {
  background: var(--accent);
}
.sw-miss {
  background: color-mix(in srgb, var(--muted) 45%, transparent);
}
.sw-tick {
  background: var(--text);
  height: 3px;
  vertical-align: 3px;
}
.sw-up {
  border: 1.5px dashed var(--accent);
}
</style>
