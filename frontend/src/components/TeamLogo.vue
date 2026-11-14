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
    class="inline-block shrink-0 object-contain align-middle"
    :style="{ width: `${size}px`, height: `${size}px` }"
    loading="lazy"
    @error="failed = true"
  />
  <span
    v-else
    class="inline-grid shrink-0 place-items-center rounded-full align-middle text-[8px] font-extrabold tracking-[-0.02em] text-white"
    :style="{ width: `${size}px`, height: `${size}px`, background: info?.color || 'var(--surface-3)' }"
    :title="info?.name ?? abbr"
    >{{ abbr }}</span
  >
</template>
