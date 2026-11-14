<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type Accuracy, type AccuracyPick } from '../lib/api'
import { POSITION_NAMES } from '../lib/format'
import { loadSummary } from '../lib/summary'
import PosChip from '../components/PosChip.vue'

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

function miss(p: AccuracyPick) {
  return (p.actual - p.projected).toFixed(1)
}
</script>

<template>
  <section>
    <div class="hero">
      <div class="eyebrow">{{ data?.season ?? '' }} season · PPR</div>
      <h1>The <span>scorecard</span></h1>
      <p>
        Every projection we publish is saved, then graded against the real box score. No cherry-picking: this is how
        close the model has been, week by week.
      </p>
    </div>

    <div v-if="error" class="card state state-error page-state" role="alert">
      <span class="state-icon" aria-hidden="true">!</span>
      <span class="state-title">Couldn't load the scorecard</span>
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!data" class="card state page-state" aria-busy="true">
      <span class="spinner" aria-hidden="true" />
      Loading the scorecard…
    </div>
    <div v-else-if="!overall" class="card state page-state">
      <span class="state-icon" aria-hidden="true">🏈</span>
      <span class="state-title">No graded games yet</span>
      <span>Check back after the first week of the season is played.</span>
    </div>
    <template v-else>
      <div class="tiles">
        <div class="card tile">
          <div class="tile-label">Average miss</div>
          <div class="tile-value">±{{ overall.mae.toFixed(2) }}</div>
          <div class="tile-note">Fantasy points per player-game</div>
        </div>
        <div class="card tile">
          <div class="tile-label">Within 5 points</div>
          <div class="tile-value">{{ (overall.within_5 * 100).toFixed(0) }}%</div>
          <div class="tile-note">of {{ overall.games.toLocaleString() }} graded games</div>
        </div>
        <div class="card tile">
          <div class="tile-label">Edge vs. recent average</div>
          <div class="tile-value" :class="edge !== null && edge > 0 ? 'delta-good' : 'delta-bad'">
            {{ edge !== null ? `${edge > 0 ? '+' : ''}${edge.toFixed(1)}%` : '–' }}
          </div>
          <div class="tile-note">Lower error than each player's last-3-game average (±{{ overall.baseline_mae?.toFixed(2) }})</div>
        </div>
      </div>

      <div class="card section">
        <h2 class="section-title">Week by week</h2>
        <div class="weeks">
          <div v-for="w in data.weeks" :key="w.week" class="week-row">
            <span class="week-label">Wk {{ w.week }}</span>
            <span class="week-bars">
              <span class="week-bar model" :style="{ width: `${(w.mae / maxWeekMae) * 82}%` }">
                <span>±{{ w.mae.toFixed(2) }}</span>
              </span>
              <span v-if="w.baseline_mae" class="week-bar base" :style="{ width: `${(w.baseline_mae / maxWeekMae) * 82}%` }">
                <span>±{{ w.baseline_mae.toFixed(2) }}</span>
              </span>
            </span>
            <span class="week-meta">{{ w.games }} games · {{ (w.within_5 * 100).toFixed(0) }}% within 5</span>
          </div>
        </div>
        <div class="legend">
          <span><i class="sw sw-model" /> Our average miss</span>
          <span><i class="sw sw-base" /> Last-3-game average's miss</span>
          <span>Shorter is better.</span>
        </div>
      </div>

      <div class="card section section-flush">
        <h2 class="section-title">By position</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Position</th>
                <th class="num">Games</th>
                <th class="num">Avg miss</th>
                <th class="num hide-sm">Within 5 pts</th>
                <th class="num">Last-3 avg miss</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, pos) in data.by_position" :key="pos">
                <td><PosChip :pos="String(pos)" /> <span class="hide-sm muted pos-name">{{ POSITION_NAMES[pos] }}</span></td>
                <td class="num">{{ m.games.toLocaleString() }}</td>
                <td class="num"><strong>±{{ m.mae.toFixed(2) }}</strong></td>
                <td class="num hide-sm">{{ (m.within_5 * 100).toFixed(0) }}%</td>
                <td class="num muted">{{ m.baseline_mae ? `±${m.baseline_mae.toFixed(2)}` : '–' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="split">
        <div class="card section">
          <h2 class="section-title">🎯 Best calls</h2>
          <p v-if="!data.best_calls.length" class="muted">None yet.</p>
          <RouterLink v-for="p in data.best_calls" :key="`${p.player_id}-${p.week}`" :to="`/players/${p.player_id}`" class="pick">
            <span>
              <strong>{{ p.name }}</strong>
              <span class="meta"><PosChip :pos="p.position" /> Week {{ p.week }} · {{ p.team }}</span>
            </span>
            <span class="pick-nums">
              <span class="muted">proj {{ p.projected.toFixed(1) }}</span>
              <strong>{{ p.actual.toFixed(1) }}</strong>
            </span>
          </RouterLink>
        </div>
        <div class="card section">
          <h2 class="section-title">😬 Biggest misses</h2>
          <RouterLink v-for="p in data.biggest_misses" :key="`${p.player_id}-${p.week}`" :to="`/players/${p.player_id}`" class="pick">
            <span>
              <strong>{{ p.name }}</strong>
              <span class="meta"><PosChip :pos="p.position" /> Week {{ p.week }} · {{ p.team }}</span>
            </span>
            <span class="pick-nums">
              <span class="muted">proj {{ p.projected.toFixed(1) }} → {{ p.actual.toFixed(1) }}</span>
              <strong :class="p.actual >= p.projected ? 'delta-good' : 'delta-bad'">{{ Number(miss(p)) > 0 ? '+' : '' }}{{ miss(p) }}</strong>
            </span>
          </RouterLink>
        </div>
      </div>
      <p class="muted footnote">
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

<style scoped>
.weeks {
  display: grid;
  gap: 10px;
}
.week-row {
  display: grid;
  grid-template-columns: 48px 1fr 190px;
  gap: 12px;
  align-items: center;
}
.week-label {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 16px;
}
.week-bars {
  display: grid;
  gap: 3px;
}
.week-bar {
  height: 14px;
  border-radius: 4px;
  position: relative;
  min-width: 2px;
}
.week-bar span {
  position: absolute;
  left: calc(100% + 6px);
  top: -2px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  color: var(--muted);
}
.week-bar.model {
  background: var(--bar);
}
.week-bar.base {
  background: color-mix(in srgb, var(--muted) 35%, transparent);
  height: 8px;
}
.week-bar.base span {
  top: -4px;
}
.week-meta {
  color: var(--muted);
  font-size: 12.5px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--muted);
  margin-top: 16px;
}
.sw {
  display: inline-block;
  width: 12px;
  height: 10px;
  border-radius: 3px;
  margin-right: 5px;
}
.sw-model {
  background: var(--bar);
}
.sw-base {
  background: color-mix(in srgb, var(--muted) 35%, transparent);
}
.split {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 18px;
}
.split .section {
  margin-top: 18px;
}
.pick {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 0 -10px;
  padding: 10px;
  border-radius: 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
  text-decoration: none;
  color: var(--text);
  transition: background 0.12s;
}
.pick:hover {
  background: var(--surface-2);
}
.pick:last-child {
  border-bottom: 0;
}
.pick:hover strong:first-child,
.pick:focus-visible strong:first-child {
  color: var(--accent);
}
.pick-nums {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.pick-nums strong {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.1;
}
.footnote {
  font-size: 13px;
  line-height: 1.6;
  margin-top: 18px;
  max-width: 760px;
}
@media (max-width: 720px) {
  .week-row {
    grid-template-columns: 40px 1fr;
  }
  .week-meta {
    grid-column: 2;
    text-align: left;
    margin-top: -4px;
  }
}
</style>
