<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api, type PredictionRow } from '../lib/api'
import { byeFlag, injuryClass, injuryShort, points, relativeTime, SCORING_NAMES } from '../lib/format'
import { scoring } from '../lib/store'
import { loadSummary, summary, summaryError, team } from '../lib/summary'
import PlayerAvatar from '../components/PlayerAvatar.vue'
import PosChip from '../components/PosChip.vue'
import TeamLogo from '../components/TeamLogo.vue'
import PageHero from '../components/PageHero.vue'
import StateMessage from '../components/StateMessage.vue'

type SortKey = 'projected' | 'recent' | 'name' | 'team' | 'actual'
const SORT_KEYS: SortKey[] = ['projected', 'recent', 'name', 'team', 'actual']
const PAGE_SIZE = 50

const route = useRoute()
const router = useRouter()

// Filters start from the URL (?week=2026-9&pos=WR&q=chase&sort=name) so refresh and Back keep them.
function queryValue(key: string): string {
  const value = route.query[key]
  return typeof value === 'string' ? value : ''
}
const initialSort = queryValue('sort') as SortKey

const rows = ref<PredictionRow[]>([])
const loading = ref(true)
const error = ref('')
const position = ref(queryValue('pos').toUpperCase() || 'ALL')
const search = ref(queryValue('q'))
const hideOut = ref(true)
const sortKey = ref<SortKey>(SORT_KEYS.includes(initialSort) ? initialSort : 'projected')
const selectedWeek = ref('')
const limit = ref(PAGE_SIZE)

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
const shown = computed(() => visible.value.slice(0, limit.value))
const remaining = computed(() => visible.value.length - shown.value.length)
// Upcoming bye weeks for the rows on screen, keyed by player.
const byes = computed(() => new Map(shown.value.map((r) => [r.player_id, byeFlag(r.bye_week, current.value.week)])))
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
  if (!s?.season || !s.week) {
    loading.value = false
    return
  }
  const fromUrl = queryValue('week')
  const known = (s.weeks ?? []).some((w) => `${w.season}-${w.week}` === fromUrl)
  selectedWeek.value = known ? fromUrl : `${s.season}-${s.week}`
  if (position.value !== 'ALL' && !(s.positions ?? []).includes(position.value)) position.value = 'ALL'
})

watch([selectedWeek, scoring], loadRows)

// Mirror the filters into the URL without adding history entries.
watch([selectedWeek, position, search, sortKey], () => {
  if (!selectedWeek.value) return
  const query: Record<string, string> = {}
  if (selectedWeek.value !== targetKey.value) query.week = selectedWeek.value
  if (position.value !== 'ALL') query.pos = position.value
  if (search.value.trim()) query.q = search.value.trim()
  if (sortKey.value !== 'projected') query.sort = sortKey.value
  router.replace({ query })
})

// Start from the top of the list whenever the filters change.
watch([selectedWeek, position, search, sortKey, hideOut, scoring], () => {
  limit.value = PAGE_SIZE
})
watch(isPastWeek, (past) => {
  if (!past && sortKey.value === 'actual') sortKey.value = 'projected'
})

function clearFilters() {
  search.value = ''
  position.value = 'ALL'
}

function diffClass(row: PredictionRow) {
  if (row.actual === null) return ''
  return row.actual >= row.projected ? 'text-good' : 'text-bad'
}

// Repeated class lists, kept here so the template stays readable.
const statValue = 'font-display text-[30px] leading-none font-bold tabular-nums'
const statLabel = 'mt-1 text-[12px] tracking-[0.08em] text-hero-muted uppercase'
const meta = 'mt-0.5 flex items-center gap-1.5 text-[12.5px] text-muted'
const rankCell = 'w-11 font-display text-[17px] font-bold text-muted max-tab:w-[30px] max-tab:text-[15px]'
const projection = 'font-display text-[24px] leading-none font-extrabold tabular-nums max-tab:text-[20px]'
const heroSkeleton = 'inline-block animate-pulse rounded-md bg-white/15 align-middle'
</script>

<template>
  <section>
    <PageHero :eyebrow="current.season ? `${current.season} season · ${SCORING_NAMES[scoring]} scoring` : `${SCORING_NAMES[scoring]} scoring`">
      <template #title>
        Week
        <span v-if="current.week">{{ current.week }}</span>
        <span v-else :class="heroSkeleton" class="h-[0.75em] w-[1.1em]" aria-label="Loading week" />
        projections
      </template>
      <p v-if="isPastWeek">This week is in the books. Here's what we projected next to what actually happened.</p>
      <p v-else>
        AI projections for every QB, RB, WR, TE and defense, rebuilt every morning with the latest stats, Vegas lines
        and injury reports.
      </p>
      <template #after>
        <div
          class="mt-[22px] flex flex-wrap gap-x-9 gap-y-3 border-t border-white/12 pt-[18px] max-tab:gap-x-5 [&>div+div]:border-l [&>div+div]:border-white/12 [&>div+div]:pl-9 max-tab:[&>div+div]:border-l-0 max-tab:[&>div+div]:pl-0"
        >
          <div>
            <div :class="statValue">
              <span v-if="!loading">{{ rows.length || '–' }}</span>
              <span v-else :class="heroSkeleton" class="h-[30px] w-14" />
            </div>
            <div :class="statLabel">Players projected</div>
          </div>
          <div v-if="summary?.model?.metrics?.model_mae">
            <div :class="statValue">±{{ summary.model.metrics.model_mae.toFixed(1) }}</div>
            <div :class="statLabel">Avg miss, {{ summary.model.metrics.holdout_season }} test</div>
          </div>
          <div>
            <div :class="statValue">
              <span v-if="summary">{{ relativeTime(summary.last_refreshed) }}</span>
              <span v-else :class="heroSkeleton" class="h-[30px] w-24" />
            </div>
            <div :class="statLabel">Last updated</div>
          </div>
        </div>
      </template>
    </PageHero>


    <div
      class="sticky top-(--header-h,60px) z-10 -mx-2 mt-4 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-2.5 bg-bg/88 px-2 py-2.5 backdrop-blur-md"
    >
      <div
        class="inline-flex flex-wrap gap-1.5 max-tab:max-w-full max-tab:flex-nowrap max-tab:overflow-x-auto max-tab:[scrollbar-width:none]"
        role="tablist"
        aria-label="Position"
      >
        <button
          v-for="pos in ['ALL', ...(summary?.positions ?? [])]"
          :key="pos"
          type="button"
          role="tab"
          class="pill"
          :class="{ 'pill-on': position === pos }"
          :aria-selected="position === pos"
          @click="position = pos"
        >
          {{ pos === 'ALL' ? 'All' : pos === 'DST' ? 'D/ST' : pos }}
        </button>
      </div>
      <input
        v-model="search"
        class="control control-search max-w-[300px] min-w-[170px] flex-1 max-tab:order-first max-tab:max-w-none max-tab:basis-full"
        type="search"
        placeholder="Search players or teams"
        aria-label="Search"
      />
      <select v-model="sortKey" class="control control-select max-tab:flex-1" aria-label="Sort by">
        <option value="projected">Sort: Projection</option>
        <option value="recent">Sort: Last 3 games</option>
        <option value="name">Sort: Name</option>
        <option value="team">Sort: Team</option>
        <option v-if="showActual" value="actual">Sort: Actual</option>
      </select>
      <select
        v-if="weekOptions.length > 1"
        v-model="selectedWeek"
        class="control control-select max-tab:flex-1"
        aria-label="Week"
      >
        <option v-for="w in weekOptions" :key="w.value" :value="w.value">{{ w.label }}</option>
      </select>
      <label
        class="inline-flex min-h-9 cursor-pointer items-center gap-2 text-[14px] font-medium text-muted select-none hover:text-fg"
      >
        <input v-model="hideOut" type="checkbox" class="m-0 size-4 cursor-pointer accent-accent" /> Hide players ruled
        out
      </label>
      <span
        v-if="!loading && !error && rows.length"
        class="ml-auto text-[13px] font-semibold whitespace-nowrap text-muted tabular-nums max-tab:hidden"
        aria-live="polite"
      >
        {{ visible.length }} of {{ rows.length }} players
      </span>
    </div>

    <div class="card">
      <StateMessage v-if="error || summaryError" kind="error" title="Couldn't load projections">
        <span>{{ error || summaryError }}</span>
      </StateMessage>
      <div v-else-if="loading" class="py-2" aria-busy="true" aria-label="Loading projections">
        <div
          v-for="n in 8"
          :key="n"
          class="flex items-center gap-3.5 border-b border-line/70 px-5 py-3 last:border-b-0 max-tab:px-3"
        >
          <span class="skeleton h-4 w-[18px]" />
          <span class="skeleton size-[38px] shrink-0 rounded-full!" />
          <span class="grid flex-1 gap-[7px]">
            <span class="skeleton h-3 max-w-full" :style="{ width: `${150 - (n % 3) * 22}px` }" />
            <span class="skeleton h-2.5 w-20" />
          </span>
          <span class="skeleton h-[22px] w-[46px]" />
        </div>
      </div>
      <StateMessage
        v-else-if="!visible.length"
        :icon="rows.length ? '🔍' : '🏈'"
        :title="rows.length ? 'No players match those filters' : 'No projections yet'"
      >
        <span>{{ rows.length ? 'Try another position or clear the search.' : 'The first data refresh may still be running.' }}</span>
        <button
          v-if="rows.length && (search || position !== 'ALL')"
          type="button"
          class="pill mt-2.5"
          @click="clearFilters"
        >
          Clear filters
        </button>
      </StateMessage>
      <div v-else class="overflow-x-auto rounded-[inherit]">
        <table class="data-table">
          <thead>
            <tr>
              <th :class="rankCell">#</th>
              <th>Player</th>
              <th class="max-tab:hidden">Matchup</th>
              <th class="text-right max-tab:hidden">Last 3 avg</th>
              <th class="text-right">Projected</th>
              <th v-if="showActual" class="text-right">Actual</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in shown"
              :key="row.player_id"
              class="group/row"
              :style="{ '--team': team(row.team)?.color || 'transparent' }"
            >
              <td :class="rankCell" class="shadow-[inset_4px_0_0_var(--team)] group-hover/row:text-fg">{{ i + 1 }}</td>
              <td>
                <RouterLink
                  :to="`/players/${row.player_id}`"
                  class="group/player flex items-center gap-3 rounded-md text-fg no-underline focus-visible:outline-offset-4 max-tab:gap-[9px]"
                >
                  <PlayerAvatar :src="row.headshot_url" :name="row.name" :team-abbr="row.team" :size="38" />
                  <span>
                    <span
                      class="font-bold transition-colors duration-[120ms] group-hover/player:text-accent group-focus-visible/player:text-accent"
                      >{{ row.name }}</span
                    >
                    <span
                      v-if="row.injury_status"
                      class="ml-1.5 inline-block rounded-sm px-[5px] py-px align-[1px] text-[10.5px] font-extrabold tracking-[0.03em]"
                      :class="injuryClass(row.injury_status)"
                      :title="`${row.injury_status}${row.injury ? ` (${row.injury})` : ''}`"
                      >{{ injuryShort(row.injury_status) }}</span
                    >
                    <span
                      v-if="byes.get(row.player_id)?.soon"
                      class="ml-1.5 inline-block rounded-sm bg-accent-soft px-[5px] py-px align-[1px] text-[10.5px] font-extrabold tracking-[0.03em] text-accent uppercase"
                      :title="byes.get(row.player_id)?.title"
                      >{{ byes.get(row.player_id)?.label }}</span
                    >
                    <span :class="meta">
                      <PosChip :pos="row.position" />
                      <span>{{ row.position }}{{ positionRank.get(row.player_id) }}</span>
                      <span>· {{ row.team }}</span>
                      <span class="hidden max-tab:inline">· {{ row.is_home ? 'vs' : '@' }} {{ row.opponent }}</span>
                      <span
                        v-if="byes.get(row.player_id) && !byes.get(row.player_id)?.soon"
                        class="max-tab:hidden"
                        :title="byes.get(row.player_id)?.title"
                        >· {{ byes.get(row.player_id)?.label }}</span
                      >
                    </span>
                  </span>
                </RouterLink>
              </td>
              <td class="max-tab:hidden">
                <span class="inline-flex items-center gap-2 font-semibold text-muted">
                  <span>{{ row.is_home ? 'vs' : '@' }}</span>
                  <TeamLogo :abbr="row.opponent" :size="24" />
                  {{ row.opponent }}
                </span>
              </td>
              <td class="text-right text-muted max-tab:hidden">
                {{ row.recent_avg_ppr !== null ? points(row.recent_avg_ppr) : '–' }}
              </td>
              <td class="text-right" :class="{ 'opacity-45': row.injury_status === 'Out' }">
                <div :class="projection" :title="row.injury_status === 'Out' ? 'Ruled out this week' : undefined">
                  {{ points(row.projected) }}
                </div>
                <div
                  class="mt-1.5 ml-auto h-1 rounded-xs bg-bar"
                  :style="{ width: `${(row.projected / maxProjection) * 72}px` }"
                />
              </td>
              <td v-if="showActual" class="text-right">
                <span v-if="row.actual !== null" :class="[projection, diffClass(row)]">{{ points(row.actual) }}</span>
                <span v-else class="text-muted">{{ isPastWeek ? 'DNP' : '–' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="remaining > 0" class="flex justify-center border-t border-line/70 px-5 py-4">
          <button type="button" class="pill" @click="limit += PAGE_SIZE">
            Show {{ Math.min(PAGE_SIZE, remaining) }} more
            <span class="font-semibold text-muted">· {{ remaining }} left</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
