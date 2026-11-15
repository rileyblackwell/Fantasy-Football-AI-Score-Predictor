<script setup lang="ts">
// Search box for the Trade Analyzer: suggests players by name or team with their rest-of-season points.
import { computed, ref, useId } from 'vue'
import { points } from '../lib/format'
import { type RosPlayer, searchPool } from '../lib/trade'
import PlayerAvatar from './PlayerAvatar.vue'
import PosChip from './PosChip.vue'

const props = withDefaults(defineProps<{ pool: RosPlayer[]; exclude?: string[]; placeholder?: string }>(), {
  exclude: () => [],
  placeholder: 'Search for a player',
})
const emit = defineEmits<{ pick: [player: RosPlayer] }>()

const query = ref('')
const open = ref(false)
const active = ref(0)
const listId = useId()

const results = computed(() => searchPool(props.pool, query.value, props.exclude))
const expanded = computed(() => open.value && query.value.trim().length > 0)

function choose(player: RosPlayer | undefined) {
  if (!player) return
  emit('pick', player)
  query.value = ''
  active.value = 0
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    open.value = true
    const n = results.value.length
    if (n) active.value = (active.value + (e.key === 'ArrowDown' ? 1 : -1) + n) % n
  } else if (e.key === 'Enter') {
    if (expanded.value && results.value.length) {
      e.preventDefault()
      choose(results.value[active.value])
    }
  } else if (e.key === 'Escape') {
    open.value = false
  }
}
</script>

<template>
  <div class="relative">
    <input
      v-model="query"
      class="control control-search w-full"
      type="search"
      role="combobox"
      autocomplete="off"
      :placeholder="placeholder"
      :aria-label="placeholder"
      :aria-expanded="expanded"
      :aria-controls="listId"
      aria-autocomplete="list"
      :aria-activedescendant="expanded && results.length ? `${listId}-${active}` : undefined"
      @input="(open = true), (active = 0)"
      @focus="open = true"
      @blur="open = false"
      @keydown="onKeydown"
    />
    <ul
      v-show="expanded"
      :id="listId"
      role="listbox"
      class="card absolute inset-x-0 top-[calc(100%+6px)] z-30 m-0 max-h-[340px] list-none overflow-y-auto p-1.5"
    >
      <li
        v-for="(p, i) in results"
        :id="`${listId}-${i}`"
        :key="p.player_id"
        role="option"
        :aria-selected="i === active"
        class="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2"
        :class="i === active ? 'bg-surface-3' : ''"
        @mouseenter="active = i"
        @mousedown.prevent="choose(p)"
      >
        <PlayerAvatar :src="p.headshot_url" :name="p.name" :team-abbr="p.team" :size="30" />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-[14px] font-bold">{{ p.name }}</span>
          <span class="flex items-center gap-1.5 text-[12px] text-muted">
            <PosChip :pos="p.position" />
            {{ p.team || 'FA' }} · {{ p.games_left }} game{{ p.games_left === 1 ? '' : 's' }} left
          </span>
        </span>
        <span class="text-right">
          <span class="block font-display text-[18px] leading-none font-bold tabular-nums">{{ points(p.total) }}</span>
          <span class="text-[11px] text-muted">rest of season</span>
        </span>
      </li>
      <li v-if="!results.length" role="presentation" class="px-2.5 py-3 text-[14px] text-muted">
        No players match "{{ query.trim() }}"
      </li>
    </ul>
  </div>
</template>
