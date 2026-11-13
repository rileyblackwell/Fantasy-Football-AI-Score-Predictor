<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type PredictionRow } from '../lib/api'
import { injuryClass, injuryShort, relativeTime, SCORING_NAMES } from '../lib/format'
import { scoring } from '../lib/store'
import { loadSummary, summary, summaryError, team } from '../lib/summary'
import PlayerAvatar from '../components/PlayerAvatar.vue'
import PosChip from '../components/PosChip.vue'
import TeamLogo from '../components/TeamLogo.vue'

type SortKey = 'projected' | 'recent' | 'name' | 'team' | 'actual'

const rows = ref<PredictionRow[]>([])
const loading = ref(true)
const error = ref('')
const position = ref('ALL')
const search = ref('')
const hideOut = ref(true)
const sortKey = ref<SortKey>('projected')
const selectedWeek = ref('')

const targetKey = computed(() => (summary.value?.season ? `${summary.value.season}-${summary.value.week}` : ''))

const weekOptions = computed(() => {
  const seen = new Set<string>()
  return (summary.value?.weeks ?? [])
    .map((w) => `${w.season}-${w.week}`)
    .filter((key) => (seen.has(key) ? false : (seen.add(key), true)))
    .map((key) => ({ value: key, label: `Week ${key.split('-')[1]}${key === targetKey.value ? ' · upcoming' : ''}` }))
})

const current = computed(() => {
  const [season, week] = selectedWeek.value.split('-').map(Number)
  return { season, week }
})
const isPastWeek = computed(() => !!targetKey.value && selectedWeek.value !== targetKey.value)
const showActual = computed(() => rows.value.some((r) => r.actual !== null))

const sorters: Record<SortKey, (a: PredictionRow, b: PredictionRow) => number> = {
  projected: (a, b) => b.projected - a.projected,
  recent: (a, b) => (b.recent_avg_ppr ?? -1) - (a.recent_avg_ppr ?? -1),
  name: (a, b) => a.name.localeCompare(b.name),
  team: (a, b) => a.team.localeCompare(b.team) || b.projected - a.projected,
  actual: (a, b) => (b.actual ?? -99) - (a.actual ?? -99),
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return rows.value.filter(
    (r) =>
      (position.value === 'ALL' || r.position === position.value) &&
      (!hideOut.value || r.injury_status !== 'Out') &&
      (!q ||
        r.name.toLowerCase().includes(q) ||
        r.team.toLowerCase() === q ||
        (team(r.team)?.nickname ?? '').toLowerCase().includes(q)),
  )
})

// Positional rank (e.g. WR7) is always by projection, whatever the table is sorted by.
const positionRank = computed(() => {
  const counters: Record<string, number> = {}
  const ranks = new Map<string, number>()
  for (const r of [...rows.value].sort(sorters.projected)) {
    counters[r.position] = (counters[r.position] ?? 0) + 1
    ranks.set(r.player_id, counters[r.position])
  }
  return ranks
})

const visible = computed(() => [...filtered.value].sort(sorters[sortKey.value]))
const spotlight = computed(() => [...filtered.value].sort(sorters.projected).slice(0, 3))
const maxProjection = computed(() => Math.max(1, ...rows.value.map((r) => r.projected)))

async function loadRows() {
  if (!selectedWeek.value) return
  loading.value = true
  error.value = ''
  try {
    rows.value = (await api.predictions({ ...current.value, scoring: scoring.value })).results
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

loadSummary().then((s) => {
  if (s?.season && s.week) selectedWeek.value = `${s.season}-${s.week}`
  else loading.value = false
})

watch([selectedWeek, scoring], loadRows)
watch(isPastWeek, (past) => {
  if (!past && sortKey.value === 'actual') sortKey.value = 'projected'
})

function diffClass(row: PredictionRow) {
  if (row.actual === null) return ''
  return row.actual >= row.projected ? 'delta-good' : 'delta-bad'
}
</script>

<template>
  <section>
    <div class="hero">
      <div class="eyebrow">{{ current.season || '' }} season · {{ SCORING_NAMES[scoring] }} scoring</div>
      <h1>
        Week <span>{{ current.week || '–' }}</span> projections
      </h1>
      <p v-if="isPastWeek">This week is in the books. Here's what we projected next to what actually happened.</p>
      <p v-else>
        AI projections for every QB, RB, WR, TE and defense, rebuilt every morning with the latest stats, Vegas lines
        and injury reports.
      </p>
      <div class="hero-stats">
        <div>
          <div class="hero-stat-value">{{ rows.length || '–' }}</div>
          <div class="hero-stat-label">Players projected</div>
        </div>
        <div v-if="summary?.model?.metrics?.model_mae">
          <div class="hero-stat-value">±{{ summary.model.metrics.model_mae.toFixed(1) }}</div>
          <div class="hero-stat-label">Avg miss, {{ summary.model.metrics.holdout_season }} test</div>
        </div>
        <div>
          <div class="hero-stat-value">{{ relativeTime(summary?.last_refreshed ?? null) }}</div>
          <div class="hero-stat-label">Last updated</div>
        </div>
      </div>
    </div>

    <div v-if="spotlight.length && !loading && !error" class="spotlight">
      <RouterLink
        v-for="(row, i) in spotlight"
        :key="row.player_id"
        :to="`/players/${row.player_id}`"
        class="spot card"
        :style="{ '--team': team(row.team)?.color || 'var(--accent)' }"
      >
        <span class="spot-rank">#{{ i + 1 }}</span>
        <PlayerAvatar :src="row.headshot_url" :name="row.name" :team-abbr="row.team" :size="56" />
        <span class="spot-body">
          <span class="spot-name">{{ row.name }}</span>
          <span class="meta">
            <PosChip :pos="row.position" />
            {{ row.is_home ? 'vs' : '@' }} {{ row.opponent }}
          </span>
        </span>
        <span class="spot-points">
          {{ row.projected.toFixed(1) }}
          <small>pts</small>
        </span>
      </RouterLink>
    </div>

    <div class="toolbar">
      <div class="pills" role="tablist" aria-label="Position">
        <button
          v-for="pos in ['ALL', ...(summary?.positions ?? [])]"
          :key="pos"
          type="button"
          role="tab"
          class="pill"
          :class="{ on: position === pos }"
          :aria-selected="position === pos"
          @click="position = pos"
        >
          {{ pos === 'ALL' ? 'All' : pos === 'DST' ? 'D/ST' : pos }}
        </button>
      </div>
      <input v-model="search" class="input" type="search" placeholder="Search players or teams" aria-label="Search" />
      <select v-model="sortKey" class="select" aria-label="Sort by">
        <option value="projected">Sort: Projection</option>
        <option value="recent">Sort: Last 3 games</option>
        <option value="name">Sort: Name</option>
        <option value="team">Sort: Team</option>
        <option v-if="showActual" value="actual">Sort: Actual</option>
      </select>
      <select v-if="weekOptions.length > 1" v-model="selectedWeek" class="select" aria-label="Week">
        <option v-for="w in weekOptions" :key="w.value" :value="w.value">{{ w.label }}</option>
      </select>
      <label class="check"><input v-model="hideOut" type="checkbox" /> Hide players ruled out</label>
    </div>

    <div class="card">
      <div v-if="error || summaryError" class="state">Couldn't load projections: {{ error || summaryError }}</div>
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
            <tr
              v-for="(row, i) in visible"
              :key="row.player_id"
              class="team-row"
              :style="{ '--team': team(row.team)?.color || 'transparent' }"
            >
              <td class="rank">{{ i + 1 }}</td>
              <td>
                <RouterLink :to="`/players/${row.player_id}`" class="player-cell">
                  <PlayerAvatar :src="row.headshot_url" :name="row.name" :team-abbr="row.team" :size="38" />
                  <span>
                    <span class="player-name">{{ row.name }}</span>
                    <span
                      v-if="row.injury_status"
                      class="badge"
                      :class="injuryClass(row.injury_status)"
                      :title="`${row.injury_status}${row.injury ? ` (${row.injury})` : ''}`"
                      >{{ injuryShort(row.injury_status) }}</span
                    >
                    <span class="meta">
                      <PosChip :pos="row.position" />
                      <span>{{ row.position }}{{ positionRank.get(row.player_id) }}</span>
                      <span>· {{ row.team }}</span>
                      <span class="show-sm">· {{ row.is_home ? 'vs' : '@' }} {{ row.opponent }}</span>
                    </span>
                  </span>
                </RouterLink>
              </td>
              <td class="hide-sm">
                <span class="matchup">
                  <span class="muted">{{ row.is_home ? 'vs' : '@' }}</span>
                  <TeamLogo :abbr="row.opponent" :size="24" />
                  {{ row.opponent }}
                </span>
              </td>
              <td class="num muted hide-sm">{{ row.recent_avg_ppr?.toFixed(1) ?? '–' }}</td>
              <td class="num">
                <div class="projection">{{ row.projected.toFixed(1) }}</div>
                <div class="projection-bar" :style="{ width: `${(row.projected / maxProjection) * 72}px` }" />
              </td>
              <td v-if="showActual" class="num">
                <span v-if="row.actual !== null" class="projection" :class="diffClass(row)">{{ row.actual.toFixed(1) }}</span>
                <span v-else class="muted">{{ isPastWeek ? 'DNP' : '–' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.spotlight {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
  margin-top: 18px;
}
.spot {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  text-decoration: none;
  color: var(--text);
  overflow: hidden;
  transition: transform 0.15s, box-shadow 0.15s;
}
.spot::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 5px;
  background: var(--team);
}
.spot::after {
  content: '';
  position: absolute;
  inset: -40% -20% auto auto;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--team) 22%, transparent), transparent 70%);
  pointer-events: none;
}
.spot:hover {
  transform: translateY(-2px);
}
.spot-rank {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 22px;
  color: var(--muted);
  min-width: 26px;
}
.spot-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.spot-name {
  font-weight: 800;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.spot-points {
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 800;
  line-height: 1;
  color: var(--accent);
  text-align: right;
}
.spot-points small {
  display: block;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.team-row td:first-child {
  box-shadow: inset 4px 0 0 var(--team);
}
</style>
