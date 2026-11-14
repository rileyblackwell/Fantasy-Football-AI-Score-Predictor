<script setup lang="ts">
import { computed, ref } from 'vue'
import { team } from '../lib/summary'

const props = withDefaults(defineProps<{ src: string; name: string; teamAbbr: string; size?: number }>(), {
  size: 40,
})
const failed = ref(false)
const ring = computed(() => team(props.teamAbbr)?.color || 'var(--border)')
const initials = computed(() =>
  props.name
    .replace(' D/ST', '')
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join(''),
)
</script>

<template>
  <span
    class="relative inline-grid shrink-0 place-items-center overflow-hidden rounded-full bg-surface-3"
    :style="{ width: `${size}px`, height: `${size}px`, boxShadow: `0 0 0 2px ${ring}` }"
  >
    <img v-if="src && !failed" :src="src" alt="" loading="lazy" class="size-full object-cover" @error="failed = true" />
    <span v-else class="font-display text-[0.85em] font-bold text-muted">{{ initials }}</span>
  </span>
</template>
