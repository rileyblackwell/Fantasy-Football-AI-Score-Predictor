<script setup lang="ts">
// A search box that suggests players as you type; Enter or a click picks one.
import { computed, ref, useId } from 'vue'
import type { PredictionRow } from '../lib/api'
import { points } from '../lib/format'
import { searchPlayers } from '../lib/startSit'
import PlayerAvatar from './PlayerAvatar.vue'
import PosChip from './PosChip.vue'

const props = withDefaults(
  defineProps<{ rows: PredictionRow[]; exclude?: string[]; placeholder?: string; autofocus?: boolean }>(),
  { exclude: () => [], placeholder: 'Search for a player', autofocus: false },
)
const emit = defineEmits<{ pick: [row: PredictionRow] }>()

const query = ref('')
const open = ref(false)
const active = ref(0)
const listId = useId()

const results = computed(() => searchPlayers(props.rows, query.value, props.exclude))
const expanded = computed(() => open.value && query.value.trim().length > 0)

function choose(row: PredictionRow | undefined) {
  if (!row) return
  emit('pick', row)
  query.value = ''
  active.value = 0
}

function onInput() {
  open.value = true
  active.value = 0
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    open.value = true
    const step = e.key === 'ArrowDown' ? 1 : -1
    const n = results.value.length
    if (n) active.value = (active.value + step + n) % n
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
      :autofocus="autofocus"
      @input="onInput"
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
        v-for="(row, i) in results"
        :id="`${listId}-${i}`"
        :key="row.player_id"
        role="option"
        :aria-selected="i === active"
        class="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2"
        :class="i === active ? 'bg-surface-3' : ''"
        @mouseenter="active = i"
        @mousedown.prevent="choose(row)"
      >
        <PlayerAvatar :src="row.headshot_url" :name="row.name" :team-abbr="row.team" :size="30" />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-[14px] font-bold">{{ row.name }}</span>
          <span class="flex items-center gap-1.5 text-[12px] text-muted">
            <PosChip :pos="row.position" />
            {{ row.team }} · {{ row.is_home ? 'vs' : '@' }} {{ row.opponent }}
          </span>
        </span>
        <span class="font-display text-[18px] font-bold tabular-nums">{{ points(row.projected) }}</span>
      </li>
      <li v-if="!results.length" role="presentation" class="px-2.5 py-3 text-[14px] text-muted">
        No players playing this week match "{{ query.trim() }}"
      </li>
    </ul>
  </div>
</template>
