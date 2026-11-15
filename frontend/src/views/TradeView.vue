<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { injuryClass, injuryShort, points, SCORING_NAMES, signedPoints } from '../lib/format'
import { scoring } from '../lib/store'
import {
  basisNote,
  fetchRestOfSeason,
  judgeTrade,
  MAX_PER_SIDE,
  parseSide,
  type RosPlayer,
  type RosResponse,
  weekByWeek,
} from '../lib/trade'
import PageHero from '../components/PageHero.vue'
import PlayerAvatar from '../components/PlayerAvatar.vue'
import PosChip from '../components/PosChip.vue'
import StateMessage from '../components/StateMessage.vue'
import TradePicker from '../components/TradePicker.vue'

type Side = 'give' | 'get'

const route = useRoute()
const router = useRouter()

// Both sides and the last week live in the URL (?give=a,b&get=c&through=17) so a trade can be shared.
const give = ref<string[]>(parseSide(route.query.give))
const get = ref<string[]>(parseSide(route.query.get, give.value))
const through = ref<number | undefined>(Number(route.query.through) || undefined)

const meta = ref<Omit<RosResponse, 'players'> | null>(null)
const pool = ref<RosPlayer[]>([])
const details = ref<Record<string, RosPlayer>>({})
const loading = ref(true)
const error = ref('')

const poolById = computed(() => new Map(pool.value.map((p) => [p.player_id, p])))
const rowsFor = (ids: string[]) =>
  ids.flatMap((id) => {
    const p = details.value[id] ?? poolById.value.get(id)
    return p ? [p] : []
  })
const giveRows = computed(() => rowsFor(give.value))
const getRows = computed(() => rowsFor(get.value))
const picked = computed(() => [...give.value, ...get.value])
const ready = computed(() => giveRows.value.length > 0 && getRows.value.length > 0)
const verdict = computed(() => judgeTrade(giveRows.value, getRows.value))

const weeks = computed(() =>
  ready.value &&
  meta.value?.from_week &&
  meta.value.through_week &&
  [...giveRows.value, ...getRows.value].every((p) => p.games)
    ? weekByWeek(giveRows.value, getRows.value, meta.value.from_week, meta.value.through_week)
    : [],
)
const throughOptions = computed(() => {
  const m = meta.value
  if (!m?.from_week || !m.last_week) return []
  return Array.from({ length: m.last_week - m.from_week + 1 }, (_, i) => m.from_week! + i)
})

async function loadPool() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchRestOfSeason({ scoring: scoring.value, through: through.value })
    const { players, ...rest } = data
    meta.value = rest
    pool.value = players
    details.value = {}
    await loadDetails()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

// Week-by-week games are only fetched for the players in the trade.
async function loadDetails() {
  const missing = picked.value.filter((id) => !details.value[id]?.games)
  if (!missing.length) return
  try {
    const data = await fetchRestOfSeason({ scoring: scoring.value, through: through.value, ids: missing })
    const next = { ...details.value }
    for (const p of data.players) next[p.player_id] = p
    details.value = next
  } catch {
    /* totals from the pool still work; the week table waits for the next change */
  }
}

watch([scoring, through], loadPool, { immediate: true })
watch(picked, loadDetails)

watch([give, get, through], () => {
  const query: Record<string, string> = {}
  if (give.value.length) query.give = give.value.join(',')
  if (get.value.length) query.get = get.value.join(',')
  if (through.value && through.value !== meta.value?.last_week) query.through = String(through.value)
  router.replace({ query })
})

function add(side: Side, p: RosPlayer) {
  const list = side === 'give' ? give : get
  if (list.value.length < MAX_PER_SIDE && !picked.value.includes(p.player_id)) list.value = [...list.value, p.player_id]
}

function remove(side: Side, id: string) {
  const list = side === 'give' ? give : get
  list.value = list.value.filter((p) => p !== id)
}

function swap() {
  ;[give.value, get.value] = [get.value, give.value]
}

const sides = computed(() => [
  { key: 'give' as Side, title: 'You give', rows: giveRows.value, total: verdict.value.giveTotal },
  { key: 'get' as Side, title: 'You get', rows: getRows.value, total: verdict.value.getTotal },
])

const headline = computed(() => {
  const v = verdict.value
  if (v.outcome === 'even') return 'Even trade'
  if (v.outcome === 'gain') return v.lean === 'clear' ? 'You win this trade' : 'Slight edge to you'
  return v.lean === 'clear' ? 'You lose this trade' : 'Slight edge to them'
})

const statLabel = 'text-[11px] font-bold tracking-[0.08em] text-muted uppercase'
</script>

<template>
  <section>
    <PageHero
      :eyebrow="
        meta?.from_week
          ? `Weeks ${meta.from_week}–${meta.through_week} · ${SCORING_NAMES[scoring]} scoring`
          : `${SCORING_NAMES[scoring]} scoring`
      "
    >
      <template #title>Trade <span>analyzer</span></template>
      <p>
        Put the players you'd give up on one side and the ones you'd get on the other. Each player's projected
        points for the rest of the season count their remaining games, opponents and bye weeks.
      </p>
    </PageHero>

    <div class="mt-4 mb-3 flex flex-wrap items-center gap-x-3 gap-y-2.5">
      <label v-if="throughOptions.length > 1" class="flex items-center gap-2 text-[14px] font-semibold text-muted">
        Through
        <select
          :value="meta?.through_week"
          class="control control-select"
          aria-label="Count games through week"
          @change="through = Number(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="w in throughOptions" :key="w" :value="w">
            Week {{ w }}{{ w === meta?.last_week ? ' (season end)' : '' }}
          </option>
        </select>
      </label>
      <button v-if="picked.length" type="button" class="pill" @click="swap">Swap sides</button>
      <button v-if="picked.length" type="button" class="pill" @click="(give = []), (get = [])">Clear all</button>
    </div>

    <div v-if="error" class="card">
      <StateMessage kind="error" title="Couldn't load projections">
        <span>{{ error }}</span>
      </StateMessage>
    </div>
    <div v-else-if="loading && !pool.length" class="card">
      <StateMessage kind="loading">Loading rest-of-season projections…</StateMessage>
    </div>
    <div v-else-if="!meta?.from_week" class="card">
      <StateMessage kind="empty" title="No games left">
        <span>The season is over, so there is nothing left to project.</span>
      </StateMessage>
    </div>
    <template v-else>
      <!-- The verdict -->
      <div class="card mb-4 px-6 py-5 max-tab:px-4 max-tab:py-4" aria-live="polite">
        <template v-if="ready">
          <div :class="statLabel">{{ headline }}</div>
          <div class="mt-1 flex flex-wrap items-baseline gap-x-3">
            <div
              class="font-display text-[40px] leading-none font-extrabold tabular-nums max-tab:text-[32px]"
              :class="verdict.outcome === 'gain' ? 'text-good' : verdict.outcome === 'lose' ? 'text-bad' : ''"
            >
              {{ signedPoints(verdict.net) }} pts
            </div>
            <div class="text-[14.5px] text-muted">for the rest of the season</div>
          </div>
          <p class="mt-2.5 mb-0 text-[14.5px] text-muted">
            You'd get {{ points(verdict.getTotal) }} projected points and give up {{ points(verdict.giveTotal) }}<template
              v-if="verdict.outcome === 'even'"
              >, close enough that fit and depth should decide it.</template
            ><template v-else>.</template>
            <template v-if="getRows.length !== giveRows.length">
              It's {{ getRows.length }} for {{ giveRows.length }}, so the side with more players only gets their
              points if they'd make the starting lineup, and someone needs a roster spot.
            </template>
          </p>
        </template>
        <template v-else>
          <div class="font-bold">
            {{ picked.length ? 'Add a player to the other side.' : 'Add players to both sides to compare.' }}
          </div>
          <p class="mt-1 mb-0 text-[14px] text-muted">
            Search by name or team, like "Bijan" or "DET". Up to {{ MAX_PER_SIDE }} players a side.
          </p>
        </template>
      </div>

      <!-- The two sides -->
      <div class="grid grid-cols-2 gap-4 max-tab:grid-cols-1">
        <div v-for="side in sides" :key="side.key" class="card flex flex-col">
          <div class="flex items-baseline justify-between border-b border-line px-5 py-3.5 max-tab:px-4">
            <h2 class="m-0 font-display text-[20px] font-bold tracking-[0.02em] uppercase">{{ side.title }}</h2>
            <div v-if="side.rows.length" class="font-display text-[22px] font-bold tabular-nums">
              {{ points(side.total) }} <span class="text-[13px] font-semibold text-muted">pts</span>
            </div>
          </div>
          <ul class="m-0 list-none p-0">
            <li
              v-for="p in side.rows"
              :key="p.player_id"
              class="flex items-start gap-3 border-b border-line/70 px-5 py-3 max-tab:px-4"
            >
              <PlayerAvatar :src="p.headshot_url" :name="p.name" :team-abbr="p.team" :size="40" />
              <div class="min-w-0 flex-1">
                <RouterLink
                  :to="`/players/${p.player_id}`"
                  class="block truncate text-[15px] font-bold text-fg no-underline hover:text-accent"
                  >{{ p.name }}</RouterLink
                >
                <div class="mt-0.5 flex flex-wrap items-center gap-1.5 text-[12.5px] text-muted">
                  <PosChip :pos="p.position" />
                  {{ p.team || 'FA' }}
                  <span
                    v-if="p.injury_status"
                    class="rounded-sm px-[5px] py-px text-[10.5px] font-extrabold tracking-[0.03em]"
                    :class="injuryClass(p.injury_status)"
                    >{{ injuryShort(p.injury_status) }}</span
                  >
                  <span
                    v-if="p.bye_week"
                    class="rounded-sm bg-surface-2 px-[6px] py-px text-[10.5px] font-extrabold tracking-[0.03em] uppercase"
                    >Bye wk {{ p.bye_week }}</span
                  >
                </div>
                <div class="mt-1 text-[12.5px] text-muted">
                  {{ p.games_left }} game{{ p.games_left === 1 ? '' : 's' }} left · {{ points(p.per_game) }} per game
                </div>
                <div v-if="basisNote(p)" class="mt-0.5 text-[12px] text-muted italic">{{ basisNote(p) }}</div>
              </div>
              <div class="text-right">
                <div class="font-display text-[24px] leading-none font-extrabold tabular-nums">{{ points(p.total) }}</div>
                <button
                  type="button"
                  class="mt-1 text-[12px] font-semibold text-muted hover:text-fg"
                  :aria-label="`Remove ${p.name}`"
                  @click="remove(side.key, p.player_id)"
                >
                  Remove
                </button>
              </div>
            </li>
          </ul>
          <div class="mt-auto px-5 py-4 max-tab:px-4">
            <TradePicker
              v-if="side.rows.length < MAX_PER_SIDE"
              :pool="pool"
              :exclude="picked"
              :placeholder="side.key === 'give' ? 'Add a player you give' : 'Add a player you get'"
              @pick="(p) => add(side.key, p)"
            />
            <div v-else class="text-[13px] text-muted">That's the most for one side.</div>
          </div>
        </div>
      </div>

      <!-- Week by week -->
      <div v-if="weeks.length" class="card mt-4 overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>Week</th>
              <th class="text-right">You give</th>
              <th class="text-right">You get</th>
              <th class="text-right">Difference</th>
              <th>No game</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in weeks" :key="w.week">
              <td class="font-semibold">{{ w.week }}</td>
              <td class="text-right">{{ points(w.give) }}</td>
              <td class="text-right">{{ points(w.get) }}</td>
              <td
                class="text-right font-bold"
                :class="w.get - w.give > 0.05 ? 'text-good' : w.get - w.give < -0.05 ? 'text-bad' : 'text-muted'"
              >
                {{ signedPoints(w.get - w.give) }}
              </td>
              <td class="text-[13px] text-muted">{{ [...w.giveIdle, ...w.getIdle].join(', ') || '–' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="mt-4 mb-0 text-[13px] leading-[1.6] text-muted">
        How it works: each player starts from the model's projection for the upcoming week, then every remaining
        game is adjusted for how many points that opponent has allowed to the position this season. Bye weeks
        add nothing. A player ruled out this week scores 0 for it. Later weeks are estimates, so treat a gap of a
        few points as a coin flip.
      </p>
    </template>
  </section>
</template>
