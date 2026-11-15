<script setup lang="ts">
// A small check (within 5 points of the projection) or cross (further off) shown beside an actual score.
import { computed } from 'vue'
import { CLOSE_CALL_POINTS, grade } from '../lib/grade'

const props = defineProps<{ projected: number | null; actual: number | null }>()
const result = computed(() => grade(props.projected, props.actual))
const label = computed(() =>
  result.value === 'hit'
    ? `Within ${CLOSE_CALL_POINTS} points of the projection`
    : `More than ${CLOSE_CALL_POINTS} points off the projection`,
)
</script>

<template>
  <span
    v-if="result"
    class="inline-grid size-[18px] shrink-0 place-items-center rounded-full"
    :class="result === 'hit' ? 'bg-accent-soft text-good' : 'bg-surface-3 text-muted'"
    role="img"
    :aria-label="label"
    :title="label"
  >
    <svg viewBox="0 0 12 12" class="size-[10px]" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path v-if="result === 'hit'" d="M2.5 6.3 5 8.7 9.5 3.6" />
      <path v-else d="M3.5 3.5l5 5M8.5 3.5l-5 5" />
    </svg>
  </span>
</template>
