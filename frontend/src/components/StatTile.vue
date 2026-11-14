<script setup lang="ts">
// A labeled number card, used in rows of stats on the player, scorecard and about pages.
withDefaults(defineProps<{ label: string; value: string; accent?: boolean; valueClass?: string }>(), {
  accent: false,
  valueClass: '',
})
</script>

<template>
  <div
    class="card flex flex-col px-5 py-[18px]"
    :class="
      accent
        ? 'border-[color-mix(in_srgb,var(--accent)_35%,var(--border))]! bg-[linear-gradient(180deg,color-mix(in_srgb,var(--accent-soft)_70%,var(--surface)),var(--surface)_75%)]!'
        : ''
    "
  >
    <div class="text-[12px] font-bold tracking-[0.08em] text-muted uppercase">{{ label }}</div>
    <div
      class="mt-1.5 mb-1 font-display text-[38px] leading-[1.05] font-extrabold tabular-nums"
      :class="[accent ? 'text-accent' : '', valueClass]"
    >
      {{ value }}
    </div>
    <div class="mt-auto text-[13px] leading-[1.45] text-muted"><slot /></div>
  </div>
</template>
