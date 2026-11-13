<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, type PlayerDetail } from '../lib/api'
import { injuryClass, matchup, SCORING_LABELS } from '../lib/format'
import { scoring } from '../lib/store'
import WeekChart from './WeekChart.vue'

const route = useRoute()
const player = ref<PlayerDetail | null>(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    player.value = await api.player(String(route.params.id), scoring.value)
  } catch (e) {
    error.value = (e as Error).message
  }
}

watch([() => route.params.id, scoring], load, { immediate: true })

const upcoming = computed(() => player.value?.weeks.find((w) => w.actual === null && w.projected !== null) ?? null)
const backtestError = computed(() => {
  const pairs = (player.value?.weeks ?? []).filter((w) => w.actual !== null && w.projected !== null)
  if (!pairs.length) return null
  return pairs.reduce((sum, w) => sum + Math.abs((w.actual ?? 0) - (w.projected ?? 0)), 0) / pairs.length
})
</script>

<template>
  <section>
    <RouterLink to="/" class="back">← All projections</RouterLink>
    <div v-if="error" class="card state">Couldn't load this player: {{ error }}</div>
    <div v-else-if="!player" class="card state">Loading…</div>
    <template v-else>
      <div style="display: flex; align-items: center; gap: 16px">
        <img v-if="player.headshot_url" :src="player.headshot_url" alt="" class="avatar" style="width: 64px; height: 64px" @error="(e) => ((e.target as HTMLImageElement).style.visibility = 'hidden')" />
        <div>
          <h1>{{ player.name }}</h1>
          <p class="subtitle">{{ player.position }} · {{ player.team }} · {{ player.season }} season, {{ SCORING_LABELS[scoring] }}</p>
        </div>
      </div>

      <div class="stats-row">
        <div class="card stat">
          <div class="stat-label">Week {{ upcoming?.week ?? '–' }} projection</div>
          <div class="stat-value">{{ upcoming?.projected?.toFixed(1) ?? '–' }}</div>
          <div v-if="upcoming" class="meta">
            {{ matchup(upcoming.opponent, upcoming.is_home) }}
            <span v-if="upcoming.injury_status" class="badge" :class="injuryClass(upcoming.injury_status)">{{ upcoming.injury_status }}</span>
          </div>
        </div>
        <div class="card stat">
          <div class="stat-label">Season average</div>
          <div class="stat-value">{{ player.season_avg?.toFixed(1) ?? '–' }}</div>
          <div class="meta">{{ player.games_played }} games played</div>
        </div>
        <div class="card stat">
          <div class="stat-label">Avg miss this season</div>
          <div class="stat-value">{{ backtestError !== null ? `±${backtestError.toFixed(1)}` : '–' }}</div>
          <div class="meta">Projection vs actual, per game</div>
        </div>
      </div>

      <div class="card section">
        <h2>Projected vs actual</h2>
        <WeekChart :weeks="player.weeks" />
      </div>

      <div class="card section">
        <h2>Game log</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Wk</th>
                <th>Opp</th>
                <th class="num">Proj</th>
                <th class="num">Actual</th>
                <th class="hide-sm">Line</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in player.weeks" :key="w.week">
                <td>{{ w.week }}</td>
                <td class="muted">{{ matchup(w.opponent, w.is_home) }}</td>
                <td class="num">{{ w.projected?.toFixed(1) ?? '–' }}</td>
                <td class="num" style="font-weight: 600">{{ w.actual?.toFixed(1) ?? (w.projected !== null ? 'Upcoming' : '–') }}</td>
                <td class="hide-sm meta">
                  <template v-if="w.line">
                    <span v-if="player.position === 'QB'">{{ w.line.pass }} · {{ w.line.rush }}</span>
                    <span v-else-if="player.position === 'RB'">{{ w.line.rush }} · {{ w.line.rec }}</span>
                    <span v-else>{{ w.line.rec }}</span>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>
