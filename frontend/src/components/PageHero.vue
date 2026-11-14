<script setup lang="ts">
// The dark green banner at the top of the projections, scorecard and about pages.
// Wrap a word of the title in <span> to highlight it.
defineProps<{ eyebrow: string }>()
</script>

<template>
  <div
    class="relative overflow-hidden rounded-hero px-8 pt-8 pb-7 text-hero-fg shadow-card max-tab:px-5 max-tab:pt-6 max-tab:pb-[22px]
      bg-[repeating-linear-gradient(90deg,transparent_0_calc(10%-1px),rgb(255_255_255/6%)_calc(10%-1px)_10%),linear-gradient(120deg,var(--hero-from),var(--hero-to))]
      after:pointer-events-none after:absolute after:-right-[60px] after:-bottom-[120px] after:size-[360px] after:rounded-full
      after:bg-[radial-gradient(circle,rgb(132_204_22/28%),transparent_65%)] after:content-['']
      *:relative *:z-1"
  >
    <div class="eyebrow">{{ eyebrow }}</div>
    <h1
      class="mt-1.5 mb-2 font-display text-[clamp(38px,6vw,60px)] leading-[0.95] font-extrabold tracking-[0.005em] uppercase [&_span]:text-highlight"
    >
      <slot name="title" />
    </h1>
    <div
      class="max-w-[620px] text-[15.5px] leading-[1.55] text-pretty text-hero-muted"
    >
      <slot />
    </div>
    <slot name="after" />
  </div>
</template>
