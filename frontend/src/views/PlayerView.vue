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
import StatTile from '../components/StatTile.vue'
import StateMessage from '../components/StateMessage.vue'

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

function deltaClass(w: PlayerWeek) {
  if (w.actual === null || w.projected === null) return ''
  return w.actual >= w.projected ? 'text-good' : 'text-bad'
}

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
    <RouterLink
      to="/"
      class="mb-3.5 inline-flex items-center gap-1.5 text-[14px] font-semibold text-muted no-underline transition-[color,gap] duration-150 hover:gap-[9px] hover:text-accent"
      >← All projections</RouterLink
    >
    <div v-if="error" class="card">
      <StateMessage kind="error" title="Couldn't load this player">
        <span>{{ error }}</span>
      </StateMessage>
    </div>
    <div v-else-if="!player" class="card">
      <StateMessage kind="loading">Loading player…</StateMessage>
    </div>
    <template v-else>
      <div
        class="relative flex items-center gap-[22px] overflow-hidden rounded-hero px-8 py-7 text-white shadow-card max-tab:gap-3.5 max-tab:px-[18px] max-tab:py-5
          bg-[linear-gradient(120deg,color-mix(in_srgb,var(--team)_92%,#000),color-mix(in_srgb,var(--team)_55%,#000))]
          after:pointer-events-none after:absolute after:inset-0 after:bg-[repeating-linear-gradient(135deg,transparent_0_18px,rgb(255_255_255/4%)_18px_19px)] after:content-['']"
        :style="{ '--team': teamInfo?.color || 'var(--hero-to)' }"
      >
        <PlayerAvatar :src="player.headshot_url" :name="player.name" :team-abbr="player.team" :size="92" />
        <div class="relative z-1 min-w-0 flex-1">
          <div class="eyebrow flex items-center gap-2 text-white/80!">
            <PosChip :pos="player.position" on-dark />
            {{ teamInfo?.name ?? player.team }}
          </div>
          <h1 class="my-1.5 font-display text-[clamp(34px,6vw,54px)] leading-[0.95] font-extrabold uppercase">
            {{ player.name }}
          </h1>
          <div class="text-[14px] text-white/75">{{ player.season }} season · {{ SCORING_NAMES[scoring] }}</div>
        </div>
        <TeamLogo
          :abbr="player.team"
          :size="84"
          class="relative z-1 drop-shadow-[0_4px_12px_rgb(0_0_0/30%)] max-tab:hidden"
        />
      </div>

      <div class="mt-[18px] grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-3.5">
        <StatTile
          accent
          :label="`Week ${upcoming?.week ?? '–'} projection`"
          :value="upcoming?.projected?.toFixed(1) ?? '–'"
        >
          <template v-if="upcoming">
            {{ matchup(upcoming.opponent, upcoming.is_home) }}
            <span
              v-if="upcoming.injury_status"
              class="ml-1.5 inline-block rounded-sm px-[5px] py-px align-[1px] text-[10.5px] font-extrabold tracking-[0.03em]"
              :class="injuryClass(upcoming.injury_status)"
              >{{ upcoming.injury_status }}</span
            >
          </template>
          <template v-else>No game projected this week</template>
        </StatTile>
        <StatTile label="Season average" :value="player.season_avg?.toFixed(1) ?? '–'">
          {{ player.games_played }} games played
        </StatTile>
        <StatTile label="Best game" :value="Number.isFinite(best) ? best.toFixed(1) : '–'">
          Fantasy points this season
        </StatTile>
        <StatTile label="Our avg miss" :value="avgMiss !== null ? `±${avgMiss.toFixed(1)}` : '–'">
          Projection vs actual this season
        </StatTile>
      </div>

      <div class="card mt-[18px] px-6 py-[22px] max-tab:px-4 max-tab:py-[18px]">
        <h2 class="section-title">Projected vs actual</h2>
        <WeekChart :weeks="player.weeks" />
      </div>

      <div class="card mt-[18px] pt-[22px] pb-1.5 max-tab:pt-[18px] max-tab:pb-1">
        <h2 class="section-title px-6 max-tab:px-4">Game log</h2>
        <div class="overflow-x-auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>Wk</th>
                <th>Opponent</th>
                <th class="text-right">Proj</th>
                <th class="text-right">Actual</th>
                <th class="max-tab:hidden">Stat line</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in player.weeks" :key="w.week">
                <td class="w-11 font-display text-[17px] font-bold text-muted max-tab:w-[30px] max-tab:text-[15px]">
                  {{ w.week }}
                </td>
                <td>
                  <span class="inline-flex items-center gap-2 font-semibold text-muted">
                    <span>{{ w.is_home === null ? '' : w.is_home ? 'vs' : '@' }}</span>
                    <TeamLogo :abbr="w.opponent" :size="22" />
                    {{ w.opponent }}
                  </span>
                </td>
                <td class="text-right">{{ w.projected?.toFixed(1) ?? '–' }}</td>
                <td class="text-right">
                  <strong v-if="w.actual !== null" :class="deltaClass(w)">{{ w.actual.toFixed(1) }}</strong>
                  <span v-else class="text-muted">{{ w.projected !== null ? 'Upcoming' : '–' }}</span>
                </td>
                <td class="text-[13px] text-muted max-tab:hidden">{{ line(w) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>
