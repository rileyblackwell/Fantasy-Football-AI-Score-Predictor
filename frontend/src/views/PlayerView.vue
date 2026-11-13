<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, type PlayerDetail, type PlayerWeek } from '../lib/api'
import { injuryClass, matchup, SCORING_NAMES } from '../lib/format'
import { scoring } from '../lib/store'
import { loadSummary, team } from '../lib/summary'
import PlayerAvatar from '../components/PlayerAvatar.vue'
import PosChip from '../components/PosChip.vue'
import TeamLogo from '../components/TeamLogo.vue'
import WeekChart from './WeekChart.vue'

const route = useRoute()
const player = ref<PlayerDetail | null>(null)
const error = ref('')
loadSummary()

async function load() {
  error.value = ''
  try {
    player.value = await api.player(String(route.params.id), scoring.value)
    document.title = `${player.value.name} Projection · Fantasy Football Score Predictor`
  } catch (e) {
    error.value = (e as Error).message
  }
}

watch([() => route.params.id, scoring], load, { immediate: true })

const teamInfo = computed(() => (player.value ? team(player.value.team) : undefined))
const upcoming = computed(() => player.value?.weeks.find((w) => w.actual === null && w.projected !== null) ?? null)
const played = computed(() => (player.value?.weeks ?? []).filter((w) => w.actual !== null && w.projected !== null))
const avgMiss = computed(() =>
  played.value.length
    ? played.value.reduce((sum, w) => sum + Math.abs((w.actual ?? 0) - (w.projected ?? 0)), 0) / played.value.length
    : null,
)
const best = computed(() => Math.max(...(player.value?.weeks ?? []).map((w) => w.actual ?? -Infinity)))

function line(w: PlayerWeek): string {
  if (!w.line || !player.value) return ''
  const pos = player.value.position
  if (pos === 'DST') return w.line.dst
  if (pos === 'QB') return `${w.line.pass} · ${w.line.rush}`
  if (pos === 'RB') return `${w.line.rush} · ${w.line.rec}`
  return w.line.rec
}
</script>

<template>
  <section>
    <RouterLink to="/" class="back">← All projections</RouterLink>
    <div v-if="error" class="card state">Couldn't load this player: {{ error }}</div>
    <div v-else-if="!player" class="card state">Loading…</div>
    <template v-else>
      <div
        class="banner"
        :style="{ '--team': teamInfo?.color || 'var(--hero-to)', '--team2': teamInfo?.color2 || 'var(--hero-from)' }"
      >
        <PlayerAvatar :src="player.headshot_url" :name="player.name" :team-abbr="player.team" :size="92" />
        <div class="banner-body">
          <div class="eyebrow banner-eyebrow">
            <PosChip :pos="player.position" />
            {{ teamInfo?.name ?? player.team }}
          </div>
          <h1 class="banner-name">{{ player.name }}</h1>
          <div class="banner-sub">{{ player.season }} season · {{ SCORING_NAMES[scoring] }}</div>
        </div>
        <TeamLogo :abbr="player.team" :size="84" class="banner-logo" />
      </div>

      <div class="tiles">
        <div class="card tile tile-accent">
          <div class="tile-label">Week {{ upcoming?.week ?? '–' }} projection</div>
          <div class="tile-value">{{ upcoming?.projected?.toFixed(1) ?? '–' }}</div>
          <div v-if="upcoming" class="tile-note">
            {{ matchup(upcoming.opponent, upcoming.is_home) }}
            <span v-if="upcoming.injury_status" class="badge" :class="injuryClass(upcoming.injury_status)">{{ upcoming.injury_status }}</span>
          </div>
          <div v-else class="tile-note">No game projected this week</div>
        </div>
        <div class="card tile">
          <div class="tile-label">Season average</div>
          <div class="tile-value">{{ player.season_avg?.toFixed(1) ?? '–' }}</div>
          <div class="tile-note">{{ player.games_played }} games played</div>
        </div>
        <div class="card tile">
          <div class="tile-label">Best game</div>
          <div class="tile-value">{{ Number.isFinite(best) ? best.toFixed(1) : '–' }}</div>
          <div class="tile-note">Fantasy points this season</div>
        </div>
        <div class="card tile">
          <div class="tile-label">Our avg miss</div>
          <div class="tile-value">{{ avgMiss !== null ? `±${avgMiss.toFixed(1)}` : '–' }}</div>
          <div class="tile-note">Projection vs actual this season</div>
        </div>
      </div>

      <div class="card section">
        <h2 class="section-title">Projected vs actual</h2>
        <WeekChart :weeks="player.weeks" />
      </div>

      <div class="card section">
        <h2 class="section-title">Game log</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Wk</th>
                <th>Opponent</th>
                <th class="num">Proj</th>
                <th class="num">Actual</th>
                <th class="hide-sm">Stat line</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in player.weeks" :key="w.week">
                <td class="rank">{{ w.week }}</td>
                <td>
                  <span class="matchup">
                    <span class="muted">{{ w.is_home === null ? '' : w.is_home ? 'vs' : '@' }}</span>
                    <TeamLogo :abbr="w.opponent" :size="22" />
                    {{ w.opponent }}
                  </span>
                </td>
                <td class="num">{{ w.projected?.toFixed(1) ?? '–' }}</td>
                <td class="num">
                  <strong v-if="w.actual !== null" :class="w.projected !== null ? (w.actual >= w.projected ? 'delta-good' : 'delta-bad') : ''">{{ w.actual.toFixed(1) }}</strong>
                  <span v-else class="muted">{{ w.projected !== null ? 'Upcoming' : '–' }}</span>
                </td>
                <td class="hide-sm muted" style="font-size: 13px">{{ line(w) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.banner {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 26px 28px;
  border-radius: 20px;
  color: #fff;
  background: linear-gradient(120deg, color-mix(in srgb, var(--team) 92%, #000), color-mix(in srgb, var(--team) 55%, #000));
  box-shadow: var(--shadow);
}
.banner::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(135deg, transparent 0 18px, rgb(255 255 255 / 4%) 18px 19px);
  pointer-events: none;
}
.banner-body {
  flex: 1;
  min-width: 0;
  position: relative;
  z-index: 1;
}
.banner-eyebrow {
  color: rgb(255 255 255 / 80%);
  display: flex;
  gap: 8px;
  align-items: center;
}
.banner-eyebrow :deep(.pos-chip) {
  color: #fff;
  background: rgb(255 255 255 / 16%);
  border-color: rgb(255 255 255 / 30%);
}
.banner-name {
  font-family: var(--font-display);
  font-size: clamp(34px, 6vw, 54px);
  font-weight: 800;
  text-transform: uppercase;
  line-height: 0.95;
  margin: 6px 0;
}
.banner-sub {
  color: rgb(255 255 255 / 75%);
  font-size: 14px;
}
.banner-logo {
  position: relative;
  z-index: 1;
  filter: drop-shadow(0 4px 12px rgb(0 0 0 / 30%));
}
.tile-accent .tile-value {
  color: var(--accent);
}
@media (max-width: 720px) {
  .banner {
    padding: 20px 18px;
    gap: 14px;
  }
  .banner-logo {
    display: none;
  }
}
</style>
