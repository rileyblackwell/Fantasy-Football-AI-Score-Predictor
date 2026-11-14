<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api, type PlayerDetail, type PredictionRow } from '../lib/api'
import { byeFlag, injuryClass, injuryShort, points, SCORING_NAMES } from '../lib/format'
import { scoring } from '../lib/store'
import { loadSummary, summary, summaryError, team } from '../lib/summary'
import { MAX_PICKS, parsePicks, recentGames, recommend } from '../lib/startSit'
import PageHero from '../components/PageHero.vue'
import PlayerAvatar from '../components/PlayerAvatar.vue'
import PlayerPicker from '../components/PlayerPicker.vue'
import PosChip from '../components/PosChip.vue'
import StateMessage from '../components/StateMessage.vue'
import TeamLogo from '../components/TeamLogo.vue'

const route = useRoute()
const router = useRouter()

// Picks and week live in the URL (?p=id1,id2&week=2026-9) so a comparison can be shared.
const picks = ref<string[]>(parsePicks(route.query.p))
const selectedWeek = ref('')
const rows = ref<PredictionRow[]>([])
const details = ref<Record<string, PlayerDetail>>({})
const loading = ref(true)
const error = ref('')

const targetKey = computed(() => (summary.value?.season ? `${summary.value.season}-${summary.value.week}` : ''))
const current = computed(() => {
  const [season, week] = selectedWeek.value.split('-').map(Number)
  return { season, week }
})
const isPastWeek = computed(() => !!targetKey.value && selectedWeek.value !== targetKey.value)

const weekOptions = computed(() => {
  const seen = new Set<string>()
  return (summary.value?.weeks ?? [])
    .map((w) => `${w.season}-${w.week}`)
    .filter((key) => (seen.has(key) ? false : (seen.add(key), true)))
    .map((key) => ({ value: key, label: `Week ${key.split('-')[1]}${key === targetKey.value ? ' · upcoming' : ''}` }))
})

const byId = computed(() => new Map(rows.value.map((r) => [r.player_id, r])))

/** Each pick with this week's projection, or with only the player's details when they have no game. */
const cards = computed(() =>
  picks.value.map((id) => {
    const row = byId.value.get(id) ?? null
    const detail = details.value[id] ?? null
    return {
      id,
      row,
      detail,
      name: row?.name ?? detail?.name ?? 'Loading…',
      bye: row ? byeFlag(row.bye_week, current.value.week) : null,
      recent: detail && detail.season === current.value.season ? recentGames(detail.weeks, current.value.week) : [],
    }
  }),
)
const playing = computed(() => cards.value.flatMap((c) => (c.row ? [c.row] : [])))
const notPlaying = computed(() => cards.value.filter((c) => !c.row && !loading.value))
const verdict = computed(() => recommend(playing.value))
const runnerUp = computed(() => verdict.value.sit.find((r) => r.injury_status !== 'Out') ?? null)
const maxProjection = computed(() => Math.max(1, ...playing.value.map((r) => r.projected)))
const topScorer = computed(() =>
  isPastWeek.value
    ? ([...playing.value].filter((r) => r.actual !== null).sort((a, b) => (b.actual ?? 0) - (a.actual ?? 0))[0] ??
      null)
    : null,
)

function status(id: string): 'start' | 'sit' | 'out' | 'idle' {
  const row = byId.value.get(id)
  if (!row) return 'idle'
  if (row.injury_status === 'Out') return 'out'
  return verdict.value.start?.player_id === id && picks.value.length > 1 ? 'start' : 'sit'
}

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

// Season averages and recent games come from each player's page data.
async function loadDetails(ids: string[], refresh = false) {
  const wanted = ids.filter((id) => refresh || !details.value[id])
  const loaded = await Promise.all(wanted.map((id) => api.player(id, scoring.value).catch(() => null)))
  const next = { ...details.value }
  for (const detail of loaded) if (detail) next[detail.player_id] = detail
  details.value = next
}

loadSummary().then((s) => {
  if (!s?.season || !s.week) {
    loading.value = false
    return
  }
  const fromUrl = typeof route.query.week === 'string' ? route.query.week : ''
  const known = (s.weeks ?? []).some((w) => `${w.season}-${w.week}` === fromUrl)
  selectedWeek.value = known ? fromUrl : `${s.season}-${s.week}`
})

watch([selectedWeek, scoring], loadRows)
watch(picks, (ids) => loadDetails(ids), { immediate: true })
watch(scoring, () => loadDetails(picks.value, true))

watch([picks, selectedWeek], () => {
  const query: Record<string, string> = {}
  if (picks.value.length) query.p = picks.value.join(',')
  if (selectedWeek.value && selectedWeek.value !== targetKey.value) query.week = selectedWeek.value
  router.replace({ query })
})

function add(row: PredictionRow) {
  if (picks.value.length < MAX_PICKS && !picks.value.includes(row.player_id)) picks.value = [...picks.value, row.player_id]
}

function remove(id: string) {
  picks.value = picks.value.filter((p) => p !== id)
}

const statLabel = 'text-[11px] font-bold tracking-[0.08em] text-muted uppercase'
const badge = 'rounded-full px-2.5 py-[3px] text-[11px] font-extrabold tracking-[0.08em] uppercase'
const BADGES = {
  start: ['Start', 'bg-accent text-on-accent'],
  sit: ['Sit', 'bg-surface-3 text-muted'],
  out: ['Out', 'inj-out'],
  idle: ['No game', 'bg-surface-3 text-muted'],
} as const
</script>

<template>
  <section>
    <PageHero
      :eyebrow="
        current.week ? `Week ${current.week} · ${SCORING_NAMES[scoring]} scoring` : `${SCORING_NAMES[scoring]} scoring`
      "
    >
      <template #title>Start <span>or</span> sit</template>
      <p>Pick up to {{ MAX_PICKS }} players and see their projections side by side, with the one the model would start.</p>
    </PageHero>

    <div class="mt-4 mb-3 flex flex-wrap items-center gap-x-3 gap-y-2.5">
      <select
        v-if="weekOptions.length > 1"
        v-model="selectedWeek"
        class="control control-select max-tab:flex-1"
        aria-label="Week"
      >
        <option v-for="w in weekOptions" :key="w.value" :value="w.value">{{ w.label }}</option>
      </select>
      <button v-if="picks.length" type="button" class="pill" @click="picks = []">Clear all</button>
    </div>

    <div v-if="error || summaryError" class="card">
      <StateMessage kind="error" title="Couldn't load projections">
        <span>{{ error || summaryError }}</span>
      </StateMessage>
    </div>
    <div v-else-if="loading" class="card">
      <StateMessage kind="loading">Loading projections…</StateMessage>
    </div>
    <template v-else>
      <!-- The verdict -->
      <div class="card mb-4 px-6 py-5 max-tab:px-4 max-tab:py-4" aria-live="polite">
        <template v-if="picks.length >= 2 && verdict.start">
          <div :class="statLabel">{{ verdict.confidence === 'toss-up' ? 'Toss-up, slight edge to' : 'Start' }}</div>
          <div class="mt-1 flex items-center gap-3">
            <PlayerAvatar
              :src="verdict.start.headshot_url"
              :name="verdict.start.name"
              :team-abbr="verdict.start.team"
              :size="44"
            />
            <div class="font-display text-[32px] leading-none font-extrabold uppercase max-tab:text-[26px]">
              {{ verdict.start.name }}
            </div>
          </div>
          <p class="mt-2.5 mb-0 text-[14.5px] text-muted">
            <template v-if="runnerUp && verdict.margin !== null">
              Projected {{ points(verdict.margin) }} pts more than {{ runnerUp.name }}<template
                v-if="verdict.confidence === 'clear'"
                >.</template
              ><template v-else-if="verdict.confidence === 'lean'">, a lean rather than a lock.</template
              ><template v-else>, close enough to go with your gut.</template>
            </template>
            <template v-else>The only player you picked who is playing.</template>
            <template v-for="row in verdict.out" :key="row.player_id"> {{ row.name }} is ruled out.</template>
            <template v-for="card in notPlaying" :key="card.id"> {{ card.name }} has no game this week.</template>
          </p>
          <p v-if="topScorer" class="mt-1.5 mb-0 text-[14.5px] font-semibold">
            In the end, {{ topScorer.name }} scored the most: {{ points(topScorer.actual ?? 0) }} pts.
          </p>
        </template>
        <template v-else-if="picks.length >= 2 && !verdict.start">
          <div class="font-bold">None of these players is playing this week.</div>
        </template>
        <template v-else>
          <div class="font-bold">{{ picks.length ? 'Add one more player to compare.' : 'Pick two players to compare.' }}</div>
          <p class="mt-1 mb-0 text-[14px] text-muted">
            Search by name or team, like "Purdy" or "DET". You can compare up to {{ MAX_PICKS }}.
          </p>
        </template>
      </div>

      <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4">
        <article
          v-for="card in cards"
          :key="card.id"
          class="card flex flex-col overflow-hidden"
          :class="status(card.id) === 'start' ? 'border-accent! ring-2 ring-accent/25' : ''"
          :style="{ '--team': team(card.row?.team ?? card.detail?.team ?? '')?.color || 'var(--border)' }"
        >
          <div class="h-1.5 bg-(--team)" />
          <div class="flex flex-1 flex-col px-5 pt-4 pb-5 max-tab:px-4">
            <div class="flex items-center justify-between">
              <span :class="[badge, BADGES[status(card.id)][1]]">{{ BADGES[status(card.id)][0] }}</span>
              <button
                type="button"
                class="grid size-8 place-items-center rounded-full text-[18px] text-muted transition-colors hover:bg-surface-2 hover:text-fg"
                :aria-label="`Remove ${card.name}`"
                @click="remove(card.id)"
              >
                ×
              </button>
            </div>

            <RouterLink :to="`/players/${card.id}`" class="mt-3 flex items-center gap-3 text-fg no-underline">
              <PlayerAvatar
                :src="card.row?.headshot_url ?? card.detail?.headshot_url ?? ''"
                :name="card.name"
                :team-abbr="card.row?.team ?? card.detail?.team ?? ''"
                :size="52"
              />
              <span class="min-w-0">
                <span class="block truncate text-[17px] font-bold hover:text-accent">{{ card.name }}</span>
                <span class="mt-0.5 flex items-center gap-1.5 text-[13px] text-muted">
                  <PosChip :pos="card.row?.position ?? card.detail?.position ?? ''" />
                  {{ card.row?.team ?? card.detail?.team }}
                  <span
                    v-if="card.row?.injury_status"
                    class="rounded-sm px-[5px] py-px text-[10.5px] font-extrabold tracking-[0.03em]"
                    :class="injuryClass(card.row.injury_status)"
                    :title="`${card.row.injury_status}${card.row.injury ? ` (${card.row.injury})` : ''}`"
                    >{{ injuryShort(card.row.injury_status) }}</span
                  >
                </span>
              </span>
            </RouterLink>

            <template v-if="card.row">
              <div class="mt-4 flex items-center gap-2 text-[14px] font-semibold text-muted">
                {{ card.row.is_home ? 'vs' : '@' }}
                <TeamLogo :abbr="card.row.opponent" :size="22" />
                {{ team(card.row.opponent)?.name ?? card.row.opponent }}
              </div>
              <div
                v-if="card.bye"
                class="mt-2 self-start rounded-sm px-[6px] py-px text-[11px] font-extrabold tracking-[0.03em] uppercase"
                :class="card.bye.soon ? 'bg-accent-soft text-accent' : 'bg-surface-2 text-muted'"
                :title="card.bye.title"
              >
                {{ card.bye.label }}
              </div>
              <div class="mt-3" :class="statLabel">Projected</div>
              <div class="font-display text-[44px] leading-none font-extrabold tabular-nums">
                {{ points(card.row.projected) }}
              </div>
              <div
                class="mt-2 h-1.5 rounded-xs bg-bar"
                :style="{ width: `${(card.row.projected / maxProjection) * 100}%` }"
              />
              <div v-if="isPastWeek" class="mt-3 text-[14px]">
                <span :class="statLabel">Actual</span>
                <span
                  class="ml-2 font-display text-[22px] font-bold tabular-nums"
                  :class="card.row.actual === null ? 'text-muted' : card.row.actual >= card.row.projected ? 'text-good' : 'text-bad'"
                  >{{ card.row.actual === null ? 'DNP' : points(card.row.actual) }}</span
                >
              </div>
            </template>
            <p v-else class="mt-4 mb-4 text-[14px] text-muted">No game this week, likely a bye or inactive.</p>

            <div class="mt-auto grid grid-cols-2 gap-3 border-t border-line pt-3.5">
              <div>
                <div :class="statLabel">Last 3</div>
                <div v-if="card.recent.length" class="mt-1 flex flex-wrap gap-1 tabular-nums">
                  <span
                    v-for="g in card.recent"
                    :key="g.week"
                    class="rounded-md bg-surface-2 px-1.5 py-0.5 text-[13px] font-semibold"
                    :title="`Week ${g.week}`"
                    >{{ points(g.actual ?? 0) }}</span
                  >
                </div>
                <div v-else class="mt-1 text-[14px] text-muted">{{ card.detail ? 'No games yet' : '…' }}</div>
              </div>
              <div>
                <div :class="statLabel">Season avg</div>
                <div class="mt-1 text-[15px] font-bold tabular-nums">
                  {{ card.detail?.season_avg != null ? points(card.detail.season_avg) : '–' }}
                </div>
              </div>
            </div>
          </div>
        </article>

        <div
          v-if="picks.length < MAX_PICKS"
          class="flex min-h-[200px] flex-col justify-center gap-3 rounded-card border-2 border-dashed border-line px-5 py-6 max-tab:min-h-0"
        >
          <div class="text-[14px] font-bold">{{ picks.length ? 'Add a player' : 'Pick a player' }}</div>
          <PlayerPicker :rows="rows" :exclude="picks" @pick="add" />
        </div>
      </div>
    </template>
  </section>
</template>
