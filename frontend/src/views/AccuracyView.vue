<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type Accuracy, type AccuracyPick } from '../lib/api'
import { POSITION_NAMES } from '../lib/format'
import { loadSummary } from '../lib/summary'
import PosChip from '../components/PosChip.vue'
import PageHero from '../components/PageHero.vue'
import StatTile from '../components/StatTile.vue'
import StateMessage from '../components/StateMessage.vue'

const data = ref<Accuracy | null>(null)
const error = ref('')
loadSummary()

onMounted(async () => {
  try {
    data.value = await api.accuracy()
  } catch (e) {
    error.value = (e as Error).message
  }
})

const overall = computed(() => data.value?.overall ?? null)
const edge = computed(() => {
  const o = overall.value
  if (!o?.baseline_mae) return null
  return (1 - o.mae / o.baseline_mae) * 100
})
const maxWeekMae = computed(() => Math.max(1, ...(data.value?.weeks ?? []).flatMap((w) => [w.mae, w.baseline_mae ?? 0])))

// Repeated class lists, kept here so the template stays readable.
const section = 'card mt-[18px] px-6 py-[22px] max-tab:px-4 max-tab:py-[18px]'
const meta = 'mt-0.5 flex items-center gap-1.5 text-[12.5px] text-muted'
const pick =
  'group -mx-2.5 flex items-center justify-between gap-3 rounded-lg border-b border-line/70 p-2.5 text-fg no-underline transition-colors duration-[120ms] last:border-b-0 hover:bg-surface-2'
const pickName = 'group-hover:text-accent group-focus-visible:text-accent'
const barLabel = 'absolute left-[calc(100%+6px)] text-[11px] font-bold whitespace-nowrap text-muted'

function miss(p: AccuracyPick) {
  return (p.actual - p.projected).toFixed(1)
}
</script>

<template>
  <section>
    <PageHero :eyebrow="`${data?.season ?? ''} season · PPR`">
      <template #title>The <span>scorecard</span></template>
      <p>
        Every projection we publish is saved, then graded against the real box score. No cherry-picking: this is how
        close the model has been, week by week.
      </p>
    </PageHero>

    <div v-if="error" class="card mt-[18px]">
      <StateMessage kind="error" title="Couldn't load the scorecard">
        <span>{{ error }}</span>
      </StateMessage>
    </div>
    <div v-else-if="!data" class="card mt-[18px]">
      <StateMessage kind="loading">Loading the scorecard…</StateMessage>
    </div>
    <div v-else-if="!overall" class="card mt-[18px]">
      <StateMessage icon="🏈" title="No graded games yet">
        <span>Check back after the first week of the season is played.</span>
      </StateMessage>
    </div>
    <template v-else>
      <div class="mt-[18px] grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-3.5">
        <StatTile label="Average miss" :value="`±${overall.mae.toFixed(2)}`">Fantasy points per player-game</StatTile>
        <StatTile label="Within 5 points" :value="`${(overall.within_5 * 100).toFixed(0)}%`">
          of {{ overall.games.toLocaleString() }} graded games
        </StatTile>
        <StatTile
          label="Edge vs. recent average"
          :value="edge !== null ? `${edge > 0 ? '+' : ''}${edge.toFixed(1)}%` : '–'"
          :value-class="edge !== null && edge > 0 ? 'text-good' : 'text-bad'"
        >
          Lower error than each player's last-3-game average (±{{ overall.baseline_mae?.toFixed(2) }})
        </StatTile>
      </div>

      <div :class="section">
        <h2 class="section-title">Week by week</h2>
        <div class="grid gap-2.5">
          <div
            v-for="w in data.weeks"
            :key="w.week"
            class="grid grid-cols-[48px_1fr_190px] items-center gap-3 max-tab:grid-cols-[40px_1fr]"
          >
            <span class="font-display text-[16px] font-bold">Wk {{ w.week }}</span>
            <span class="grid gap-[3px]">
              <span class="relative h-3.5 min-w-[2px] rounded-sm bg-bar" :style="{ width: `${(w.mae / maxWeekMae) * 82}%` }">
                <span :class="barLabel" class="-top-0.5">±{{ w.mae.toFixed(2) }}</span>
              </span>
              <span
                v-if="w.baseline_mae"
                class="relative h-2 min-w-[2px] rounded-sm bg-muted/35"
                :style="{ width: `${(w.baseline_mae / maxWeekMae) * 82}%` }"
              >
                <span :class="barLabel" class="-top-1">±{{ w.baseline_mae.toFixed(2) }}</span>
              </span>
            </span>
            <span
              class="text-right text-[12.5px] text-muted tabular-nums max-tab:col-start-2 max-tab:-mt-1 max-tab:text-left"
              >{{ w.games }} games · {{ (w.within_5 * 100).toFixed(0) }}% within 5</span
            >
          </div>
        </div>
        <div class="mt-4 flex flex-wrap gap-[18px] text-[13px] text-muted">
          <span><i class="mr-[5px] inline-block h-2.5 w-3 rounded-[3px] bg-bar" /> Our average miss</span>
          <span><i class="mr-[5px] inline-block h-2.5 w-3 rounded-[3px] bg-muted/35" /> Last-3-game average's miss</span>
          <span>Shorter is better.</span>
        </div>
      </div>

      <div class="card mt-[18px] pt-[22px] pb-1.5 max-tab:pt-[18px] max-tab:pb-1">
        <h2 class="section-title px-6 max-tab:px-4">By position</h2>
        <div class="overflow-x-auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>Position</th>
                <th class="text-right">Games</th>
                <th class="text-right">Avg miss</th>
                <th class="text-right max-tab:hidden">Within 5 pts</th>
                <th class="text-right">Last-3 avg miss</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, pos) in data.by_position" :key="pos">
                <td>
                  <PosChip :pos="String(pos)" />
                  <span class="ml-2 text-muted max-tab:hidden">{{ POSITION_NAMES[pos] }}</span>
                </td>
                <td class="text-right">{{ m.games.toLocaleString() }}</td>
                <td class="text-right"><strong>±{{ m.mae.toFixed(2) }}</strong></td>
                <td class="text-right max-tab:hidden">{{ (m.within_5 * 100).toFixed(0) }}%</td>
                <td class="text-right text-muted">{{ m.baseline_mae ? `±${m.baseline_mae.toFixed(2)}` : '–' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-[18px]">
        <div :class="section">
          <h2 class="section-title">🎯 Best calls</h2>
          <p v-if="!data.best_calls.length" class="text-muted">None yet.</p>
          <RouterLink
            v-for="p in data.best_calls"
            :key="`${p.player_id}-${p.week}`"
            :to="`/players/${p.player_id}`"
            :class="pick"
          >
            <span>
              <strong :class="pickName">{{ p.name }}</strong>
              <span :class="meta"><PosChip :pos="p.position" /> Week {{ p.week }} · {{ p.team }}</span>
            </span>
            <span class="flex flex-col items-end text-[13px] tabular-nums">
              <span class="text-muted">proj {{ p.projected.toFixed(1) }}</span>
              <strong class="font-display text-[22px] leading-[1.1]">{{ p.actual.toFixed(1) }}</strong>
            </span>
          </RouterLink>
        </div>
        <div :class="section">
          <h2 class="section-title">😬 Biggest misses</h2>
          <RouterLink
            v-for="p in data.biggest_misses"
            :key="`${p.player_id}-${p.week}`"
            :to="`/players/${p.player_id}`"
            :class="pick"
          >
            <span>
              <strong :class="pickName">{{ p.name }}</strong>
              <span :class="meta"><PosChip :pos="p.position" /> Week {{ p.week }} · {{ p.team }}</span>
            </span>
            <span class="flex flex-col items-end text-[13px] tabular-nums">
              <span class="text-muted">proj {{ p.projected.toFixed(1) }} → {{ p.actual.toFixed(1) }}</span>
              <strong
                class="font-display text-[22px] leading-[1.1]"
                :class="p.actual >= p.projected ? 'text-good' : 'text-bad'"
                >{{ Number(miss(p)) > 0 ? '+' : '' }}{{ miss(p) }}</strong
              >
            </span>
          </RouterLink>
        </div>
      </div>
      <p class="mt-[18px] max-w-[760px] text-[13px] leading-[1.6] text-muted">
        <template v-if="overall.live_games">
          {{ overall.live_games.toLocaleString() }} of these games were graded against projections published before
          kickoff.
        </template>
        Weeks played before the site went live are backtested by a model that never saw this season's data; from now
        on, every published projection is locked in before kickoff and graded here.
      </p>
    </template>
  </section>
</template>
