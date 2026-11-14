<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ pos: string; onDark?: boolean }>(), { onDark: false })

// Full class names are spelled out so Tailwind can find them.
const COLORS: Record<string, string> = {
  QB: 'text-pos-qb bg-pos-qb/14 border-pos-qb/30',
  RB: 'text-pos-rb bg-pos-rb/14 border-pos-rb/30',
  WR: 'text-pos-wr bg-pos-wr/14 border-pos-wr/30',
  TE: 'text-pos-te bg-pos-te/14 border-pos-te/30',
  DST: 'text-pos-dst bg-pos-dst/14 border-pos-dst/30',
}

const colors = computed(() =>
  props.onDark ? 'text-white bg-white/16 border-white/30' : (COLORS[props.pos] ?? 'text-muted bg-surface-2 border-line'),
)
</script>

<template>
  <span
    class="inline-block min-w-[34px] rounded-[5px] border px-[5px] py-0.5 text-center text-[11px] leading-normal font-extrabold tracking-[0.03em]"
    :class="colors"
    >{{ pos === 'DST' ? 'D/ST' : pos }}</span
  >
</template>
