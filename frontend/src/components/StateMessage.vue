<script setup lang="ts">
// The loading, empty and error message shown in place of a page's content.
withDefaults(defineProps<{ kind?: 'loading' | 'empty' | 'error'; title?: string; icon?: string }>(), {
  kind: 'empty',
  title: '',
  icon: '',
})
</script>

<template>
  <div
    class="flex flex-col items-center gap-1.5 px-5 py-14 text-center text-balance text-muted"
    :role="kind === 'error' ? 'alert' : undefined"
    :aria-busy="kind === 'loading' ? 'true' : undefined"
  >
    <span
      v-if="kind === 'loading'"
      class="mb-1.5 size-[26px] animate-[spin_0.8s_linear_infinite] rounded-full border-3 border-surface-3 border-t-accent"
      aria-hidden="true"
    />
    <span
      v-else-if="kind === 'error' || icon"
      class="mb-1.5 grid size-11 place-items-center rounded-full border text-[20px]"
      :class="kind === 'error' ? 'border-bad/25 bg-bad/10 text-bad' : 'border-line bg-surface-2'"
      aria-hidden="true"
      >{{ kind === 'error' ? '!' : icon }}</span
    >
    <span v-if="title" class="text-[16px] font-bold text-fg">{{ title }}</span>
    <slot />
  </div>
</template>
