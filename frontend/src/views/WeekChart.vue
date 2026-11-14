<script setup lang="ts">
import { computed } from 'vue'
import type { PlayerWeek } from '../lib/api'

const props = defineProps<{ weeks: PlayerWeek[] }>()

const swatch = 'mr-[5px] inline-block size-3 rounded-[3px] align-[-1px]'

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
  <div>
    <svg class="block h-auto w-full" :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="Weekly fantasy points: bars are actual scores, markers are projections">
      <g v-for="t in ticks" :key="t">
        <line :x1="PAD.left" :x2="W - PAD.right" :y1="y(t)" :y2="y(t)" :class="t === 0 ? 'stroke-muted [stroke-opacity:0.5]' : 'stroke-line'" stroke-width="1" />
        <text :x="PAD.left - 8" :y="y(t) + 4" class="fill-muted font-sans text-[11px]" text-anchor="end">{{ t }}</text>
      </g>
      <g v-for="(w, i) in weeks" :key="w.week">
        <rect
          v-if="w.actual !== null"
          :x="x(i) - barW / 2"
          :width="barW"
          :y="Math.min(y(w.actual), y(0))"
          :height="Math.max(1, Math.abs(y(0) - y(w.actual)))"
          rx="4"
          :class="w.projected !== null && w.actual >= w.projected ? 'fill-accent [fill-opacity:0.85]' : 'fill-muted [fill-opacity:0.45]'"
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
          class="fill-none stroke-accent stroke-[1.5] [stroke-dasharray:4_3]"
        >
          <title>Week {{ w.week }} projection: {{ w.projected }}</title>
        </rect>
        <line
          v-if="w.projected !== null"
          :x1="x(i) - barW / 2 - 4"
          :x2="x(i) + barW / 2 + 4"
          :y1="y(w.projected)"
          :y2="y(w.projected)"
          class="stroke-fg stroke-[2.5] [stroke-linecap:round]"
        />
        <text :x="x(i)" :y="H - 10" class="fill-muted font-sans text-[11px]" text-anchor="middle">{{ w.week }}</text>
      </g>
    </svg>
    <div class="mt-2.5 flex flex-wrap gap-[18px] text-[13px] text-muted">
      <span><i :class="swatch" class="bg-accent" /> Beat projection</span>
      <span><i :class="swatch" class="bg-muted/45" /> Fell short</span>
      <span><i :class="swatch" class="h-[3px]! bg-fg align-[3px]!" /> Projection</span>
      <span><i :class="swatch" class="border-[1.5px] border-dashed border-accent" /> Upcoming</span>
    </div>
  </div>
</template>
