<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type PredictionRow, type Summary } from '../lib/api'
import { injuryClass, injuryShort, matchup, relativeTime, SCORING_LABELS } from '../lib/format'
import { scoring } from '../lib/store'

const summary = ref<Summary | null>(null)
const rows = ref<PredictionRow[]>([])
const loading = ref(true)
const error = ref('')
const position = ref('ALL')
const search = ref('')
const hideOut = ref(true)
const selectedWeek = ref('')

const weekOptions = computed(() => {
  const seen = new Set<string>()
  return (summary.value?.weeks ?? [])
    .filter((w) => {
      const key = `${w.season}-${w.week}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .map((w) => {
      const upcoming = w.season === summary.value?.season && w.week === summary.value?.week
      return { value: `${w.season}-${w.week}`, label: `Week ${w.week}${upcoming ? ' (upcoming)' : ''}` }
    })
})

const current = computed(() => {
  const [season, week] = selectedWeek.value.split('-').map(Number)
  return { season, week }
})

const isPastWeek = computed(
  () => !!summary.value && (current.value.season !== summary.value.season || current.value.week !== summary.value.week),
)
const showActual = computed(() => rows.value.some((r) => r.actual !== null))

function hideImage(event: Event) {
  ;(event.target as HTMLImageElement).style.visibility = 'hidden'
}

const visible = computed(() => {
  const q = search.value.trim().toLowerCase()
  return rows.value.filter(
    (r) =>
      (position.value === 'ALL' || r.position === position.value) &&
      (!hideOut.value || r.injury_status !== 'Out') &&
      (!q || r.name.toLowerCase().includes(q) || r.team.toLowerCase() === q),
  )
})

const maxProjection = computed(() => Math.max(1, ...rows.value.map((r) => r.projected)))

async function loadRows() {
  if (!selectedWeek.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await api.predictions({ ...current.value, scoring: scoring.value })
    rows.value = res.results
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    summary.value = await api.summary()
    if (summary.value.season && summary.value.week) {
      selectedWeek.value = `${summary.value.season}-${summary.value.week}`
    } else {
      loading.value = false
    }
  } catch (e) {
    error.value = (e as Error).message
    loading.value = false
  }
})

watch([selectedWeek, scoring], loadRows)
</script>

<template>
  <section>
    <h1>
      Week {{ current.week || '–' }} projections
      <span v-if="current.season" class="muted" style="font-weight: 500">· {{ current.season }}</span>
    </h1>
    <p class="subtitle">
      {{ SCORING_LABELS[scoring] }} scoring.
      <template v-if="isPastWeek">This week has been played, so projections sit next to actual scores.</template>
      <template v-else>Updated {{ relativeTime(summary?.last_refreshed ?? null) }}.<template v-if="showActual"> Games already played this week show the actual score.</template></template>
    </p>

    <div class="toolbar">
      <div class="tabs" role="tablist" aria-label="Position">
        <button
          v-for="pos in ['ALL', ...(summary?.positions ?? [])]"
          :key="pos"
          type="button"
          role="tab"
          class="tab"
          :class="{ on: position === pos }"
          :aria-selected="position === pos"
          @click="position = pos"
        >
          {{ pos === 'ALL' ? 'All' : pos }}
        </button>
      </div>
      <input v-model="search" class="input" type="search" placeholder="Search players" aria-label="Search" />
      <select v-if="weekOptions.length > 1" v-model="selectedWeek" class="select" aria-label="Week">
        <option v-for="w in weekOptions" :key="w.value" :value="w.value">{{ w.label }}</option>
      </select>
      <label class="check"><input v-model="hideOut" type="checkbox" /> Hide players ruled out</label>
    </div>

    <div class="card">
      <div v-if="error" class="state">Couldn't load projections: {{ error }}</div>
      <div v-else-if="loading" class="state">Loading projections…</div>
      <div v-else-if="!visible.length" class="state">
        {{ rows.length ? 'No players match those filters.' : 'No projections yet. The first data refresh may still be running.' }}
      </div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="rank">#</th>
              <th>Player</th>
              <th class="hide-sm">Matchup</th>
              <th class="num hide-sm">Last 3 avg</th>
              <th class="num">Projected</th>
              <th v-if="showActual" class="num">Actual</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in visible" :key="row.player_id">
              <td class="rank">{{ i + 1 }}</td>
              <td>
                <RouterLink :to="`/players/${row.player_id}`" class="player-cell">
                  <img v-if="row.headshot_url" :src="row.headshot_url" alt="" class="avatar" loading="lazy" @error="hideImage" />
                  <span v-else class="avatar" />
                  <span>
                    <span class="player-name">{{ row.name }}</span>
                    <span
                      v-if="row.injury_status"
                      class="badge"
                      :class="injuryClass(row.injury_status)"
                      :title="`${row.injury_status}${row.injury ? ` (${row.injury})` : ''}`"
                      >{{ injuryShort(row.injury_status) }}</span
                    >
                    <br />
                    <span class="meta"><span class="pos">{{ row.position }}</span> {{ row.team }}<span class="show-sm"> · {{ matchup(row.opponent, row.is_home) }}</span></span>
                  </span>
                </RouterLink>
              </td>
              <td class="muted hide-sm">{{ matchup(row.opponent, row.is_home) }}</td>
              <td class="num muted hide-sm">{{ row.recent_avg_ppr?.toFixed(1) ?? '–' }}</td>
              <td class="num">
                <div class="projection">{{ row.projected.toFixed(1) }}</div>
                <div class="projection-bar" :style="{ width: `${(row.projected / maxProjection) * 80}px` }" />
              </td>
              <td v-if="showActual" class="num">{{ row.actual?.toFixed(1) ?? (isPastWeek ? 'DNP' : '–') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
