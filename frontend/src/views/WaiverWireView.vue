<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { injuryClass, injuryShort, points, SCORING_NAMES, signedPoints } from '../lib/format'
import { scoring } from '../lib/store'
import { loadSummary, summaryError, team } from '../lib/summary'
import { fetchWaivers, filterWaivers, pct, pctChange, STARTER_RANK, WAIVER_POSITIONS, whyFlagged, type WaiverRow } from '../lib/waivers'
import PageHero from '../components/PageHero.vue'
import PlayerAvatar from '../components/PlayerAvatar.vue'
import PosChip from '../components/PosChip.vue'
import StateMessage from '../components/StateMessage.vue'

const route = useRoute()
const router = useRouter()

// The position filter lives in the URL (?pos=WR) so refresh and Back keep it.
const fromUrl = typeof route.query.pos === 'string' ? route.query.pos.toUpperCase() : ''
const position = ref((WAIVER_POSITIONS as readonly string[]).includes(fromUrl) ? fromUrl : 'ALL')
const hideStarters = ref(true)
const hideOut = ref(true)

const rows = ref<WaiverRow[]>([])
const meta = ref<{ season: number | null; week: number | null; through: number | null }>({
  season: null,
  week: null,
  through: null,
})
const loading = ref(true)
const error = ref('')

const visible = computed(() =>
  filterWaivers(rows.value, { position: position.value, hideStarters: hideStarters.value, hideOut: hideOut.value }),
)
const hiddenCount = computed(() => rows.value.length - visible.value.length)
const starterNote = Object.entries(STARTER_RANK)
  .map(([pos, rank]) => `${pos}${rank}`)
  .join(', ')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchWaivers({ scoring: scoring.value })
    rows.value = data.results
    meta.value = { season: data.season, week: data.week, through: data.through_week }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

loadSummary()
load()
watch(scoring, load)
watch(position, (pos) => router.replace({ query: pos === 'ALL' ? {} : { pos } }))

function historyTitle(h: WaiverRow['history'][number]): string {
  const parts: string[] = []
  if (h.snap_share !== null) parts.push(`${pct(h.snap_share)} of snaps`)
  if (h.target_share !== null) parts.push(`${pct(h.target_share)} of targets`)
  return `Week ${h.week}: ${parts.join(', ') || 'no usage data'}`
}

function barHeight(h: WaiverRow['history'][number]): string {
  const share = h.snap_share ?? h.target_share ?? 0
  return `${Math.max(8, Math.round(share * 100))}%`
}

const meta2 = 'mt-0.5 flex items-center gap-1.5 text-[12.5px] text-muted'
const shareValue = 'font-display text-[20px] leading-none font-bold tabular-nums'
const projection = 'font-display text-[24px] leading-none font-extrabold tabular-nums max-tab:text-[20px]'
</script>

<template>
  <section>
    <PageHero :eyebrow="meta.season ? `${meta.season} season · ${SCORING_NAMES[scoring]} scoring` : 'Waiver wire'">
      <template #title>Rising <span>usage</span></template>
      <p>
        Players whose share of snaps or targets has jumped over their last three games compared with earlier in the
        season. Usage tends to climb a week or two before the points do, which is the time to put in a claim.
      </p>
      <p v-if="meta.through" class="mt-2 text-[13.5px]">
        Through Week {{ meta.through }}, with Week {{ meta.week }} projections.
      </p>
    </PageHero>

    <div
      class="sticky top-(--header-h,60px) z-10 -mx-2 mt-4 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-2.5 bg-bg/88 px-2 py-2.5 backdrop-blur-md"
    >
      <div class="inline-flex flex-wrap gap-1.5" role="tablist" aria-label="Position">
        <button
          v-for="pos in ['ALL', ...WAIVER_POSITIONS]"
          :key="pos"
          type="button"
          role="tab"
          class="pill"
          :class="{ 'pill-on': position === pos }"
          :aria-selected="position === pos"
          @click="position = pos"
        >
          {{ pos === 'ALL' ? 'All' : pos }}
        </button>
      </div>
      <label
        class="inline-flex min-h-9 cursor-pointer items-center gap-2 text-[14px] font-medium text-muted select-none hover:text-fg"
        :title="`Hides players whose projection already ranks them ${starterNote} or better`"
      >
        <input v-model="hideStarters" type="checkbox" class="m-0 size-4 cursor-pointer accent-accent" /> Hide likely
        starters
      </label>
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
      <StateMessage v-if="error || summaryError" kind="error" title="Couldn't load the waiver wire">
        <span>{{ error || summaryError }}</span>
      </StateMessage>
      <StateMessage v-else-if="loading" kind="loading" title="Looking for rising players" />
      <StateMessage
        v-else-if="!visible.length"
        :icon="rows.length ? '🔍' : '📈'"
        :title="rows.length ? 'No players match those filters' : 'No rising players yet'"
      >
        <span v-if="rows.length">
          {{ hiddenCount }} flagged {{ hiddenCount === 1 ? 'player is' : 'players are' }} hidden. Try another position
          or turn off a filter.
        </span>
        <span v-else>Trends need at least five games this season, so the list fills in after the first few weeks.</span>
      </StateMessage>
      <div v-else class="overflow-x-auto rounded-[inherit]">
        <table class="data-table">
          <thead>
            <tr>
              <th>Player</th>
              <th class="max-tab:hidden">Trend</th>
              <th class="text-right">Snaps</th>
              <th class="text-right max-tab:hidden">Targets</th>
              <th class="text-right max-tab:hidden">Points, last 3</th>
              <th class="text-right">Wk {{ meta.week }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in visible"
              :key="row.player_id"
              :style="{ '--team': team(row.team)?.color || 'transparent' }"
            >
              <td class="shadow-[inset_4px_0_0_var(--team)]">
                <RouterLink
                  :to="`/players/${row.player_id}`"
                  class="group/player flex items-center gap-3 rounded-md text-fg no-underline focus-visible:outline-offset-4 max-tab:gap-[9px]"
                >
                  <PlayerAvatar :src="row.headshot_url" :name="row.name" :team-abbr="row.team" :size="38" />
                  <span>
                    <span class="font-bold transition-colors duration-[120ms] group-hover/player:text-accent">{{
                      row.name
                    }}</span>
                    <span
                      v-if="row.injury_status"
                      class="ml-1.5 inline-block rounded-sm px-[5px] py-px align-[1px] text-[10.5px] font-extrabold tracking-[0.03em]"
                      :class="injuryClass(row.injury_status)"
                      :title="`${row.injury_status}${row.injury ? ` (${row.injury})` : ''}`"
                      >{{ injuryShort(row.injury_status) }}</span
                    >
                    <span :class="meta2">
                      <PosChip :pos="row.position" />
                      <span v-if="row.position_rank">{{ row.position }}{{ row.position_rank }}</span>
                      <span>· {{ row.team }}</span>
                      <span v-if="row.opponent">· {{ row.is_home ? 'vs' : '@' }} {{ row.opponent }}</span>
                    </span>
                    <span class="mt-0.5 block text-[12.5px] font-semibold text-accent">{{ whyFlagged(row) }}</span>
                  </span>
                </RouterLink>
              </td>
              <td class="max-tab:hidden">
                <div class="flex h-9 items-end gap-[3px]" role="img" :aria-label="`Weekly usage for ${row.name}`">
                  <span
                    v-for="(h, i) in row.history"
                    :key="h.week"
                    class="w-[7px] rounded-t-[2px]"
                    :class="i >= row.history.length - row.games_recent ? 'bg-accent' : 'bg-surface-3'"
                    :style="{ height: barHeight(h) }"
                    :title="historyTitle(h)"
                  />
                </div>
              </td>
              <td class="text-right">
                <div :class="shareValue">{{ pct(row.snap_share.recent) }}</div>
                <div class="mt-1 text-[12px] font-semibold" :class="row.rising_snaps ? 'text-good' : 'text-muted'">
                  {{ pctChange(row.snap_share.change) }}
                </div>
              </td>
              <td class="text-right max-tab:hidden">
                <template v-if="row.position === 'QB'"><span class="text-muted">–</span></template>
                <template v-else>
                  <div :class="shareValue">{{ pct(row.target_share.recent) }}</div>
                  <div class="mt-1 text-[12px] font-semibold" :class="row.rising_targets ? 'text-good' : 'text-muted'">
                    {{ pctChange(row.target_share.change) }}
                  </div>
                </template>
              </td>
              <td class="text-right max-tab:hidden">
                <div :class="shareValue">{{ points(row.points_recent) }}</div>
                <div class="mt-1 text-[12px] font-semibold text-muted">
                  {{ signedPoints(row.points_recent - row.points_prior) }} vs before
                </div>
              </td>
              <td class="text-right" :class="{ 'opacity-45': row.injury_status === 'Out' }">
                <span v-if="row.projected !== null" :class="projection">{{ points(row.projected) }}</span>
                <span v-else class="text-muted" title="No game or no projection this week">–</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <p class="mt-3 text-[13px] text-muted">
      This app doesn't see your league's rosters, so "Hide likely starters" hides anyone projected as a {{ starterNote }}
      or better this week. Those players are almost always already taken.
    </p>
  </section>
</template>
