<script setup lang="ts">
defineProps<{ pos: string }>()
</script>

<template>
  <span class="pos-chip" :class="`pos-${pos.toLowerCase()}`">{{ pos === 'DST' ? 'D/ST' : pos }}</span>
</template>
