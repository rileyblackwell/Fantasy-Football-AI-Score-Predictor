<script setup lang="ts">
import { computed, ref } from 'vue'
import { team } from '../lib/summary'

const props = withDefaults(defineProps<{ abbr: string; size?: number }>(), { size: 22 })
const failed = ref(false)
const info = computed(() => team(props.abbr))
</script>

<template>
  <img
    v-if="info?.logo_url && !failed"
    :src="info.logo_url"
    :alt="info.name"
    :title="info.name"
    :width="size"
    :height="size"
    class="team-logo"
    loading="lazy"
    @error="failed = true"
  />
  <span
    v-else
    class="team-logo team-logo-fallback"
    :style="{ width: `${size}px`, height: `${size}px`, background: info?.color || 'var(--surface-3)' }"
    :title="info?.name ?? abbr"
    >{{ abbr }}</span
  >
</template>

<style scoped>
.team-logo {
  display: inline-block;
  object-fit: contain;
  vertical-align: middle;
  flex-shrink: 0;
}
.team-logo-fallback {
  border-radius: 50%;
  color: #fff;
  font-size: 8px;
  font-weight: 800;
  display: inline-grid;
  place-items: center;
  letter-spacing: -0.02em;
}
</style>
