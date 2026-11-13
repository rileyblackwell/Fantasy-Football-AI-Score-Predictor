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
  <span class="avatar" :style="{ width: `${size}px`, height: `${size}px`, '--ring': ring }">
    <img v-if="src && !failed" :src="src" alt="" loading="lazy" @error="failed = true" />
    <span v-else class="avatar-initials">{{ initials }}</span>
  </span>
</template>

<style scoped>
.avatar {
  position: relative;
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-3);
  box-shadow: 0 0 0 2px var(--ring);
  overflow: hidden;
  flex-shrink: 0;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-initials {
  font-family: var(--font-display);
  font-weight: 700;
  color: var(--muted);
  font-size: 0.85em;
}
</style>
