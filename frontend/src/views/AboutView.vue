<script setup lang="ts">
import { computed } from 'vue'
import { featureLabel, POSITION_NAMES, relativeTime } from '../lib/format'
import { loadSummary, summary, summaryError as error } from '../lib/summary'
import PosChip from '../components/PosChip.vue'
import PageHero from '../components/PageHero.vue'
import StatTile from '../components/StatTile.vue'
import StateMessage from '../components/StateMessage.vue'

loadSummary()

const model = computed(() => summary.value?.model ?? null)
const metrics = computed(() => model.value?.metrics ?? {})
const improvement = computed(() => {
  const m = metrics.value
  if (!m.model_mae || !m.baseline_mae) return null
  return ((1 - m.model_mae / m.baseline_mae) * 100).toFixed(1)
})
const section = 'card mt-[18px] px-6 py-[22px] max-tab:px-4 max-tab:py-[18px]'
const maxShare = computed(() => Math.max(0.01, ...(model.value?.feature_importance ?? []).map((f) => f.share)))
</script>

<template>
  <section>
    <PageHero eyebrow="Under the hood">
      <template #title>How the <span>AI</span> works</template>
      <p>
        A gradient-boosted machine-learning model trained on every regular-season game since 2016, retrained every
        morning.
      </p>
    </PageHero>

    <div v-if="error" class="card mt-[18px]">
      <StateMessage kind="error" title="Couldn't load model details">
        <span>{{ error }}</span>
      </StateMessage>
    </div>
    <template v-else-if="model">
      <div class="mt-[18px] grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-3.5">
        <StatTile label="Average miss (PPR points)" :value="`±${metrics.model_mae?.toFixed(2) ?? '–'}`">
          Tested on the full {{ metrics.holdout_season }} season
        </StatTile>
        <StatTile label="Better than season average" :value="improvement !== null ? `${improvement}%` : '–'">
          Baseline misses by ±{{ metrics.baseline_mae?.toFixed(2) }}
        </StatTile>
        <StatTile label="Training games" :value="model.training_rows.toLocaleString()">
          Trained in {{ model.training_seconds }}s, {{ relativeTime(model.trained_at) }}
        </StatTile>
      </div>

      <div class="card mt-[18px] pt-[22px] pb-1.5 max-tab:pt-[18px] max-tab:pb-1">
        <h2 class="section-title px-6 max-tab:px-4">Accuracy by position</h2>
        <div class="overflow-x-auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>Position</th>
                <th class="text-right">Games tested</th>
                <th class="text-right">Model miss</th>
                <th class="text-right">Season-average miss</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, pos) in metrics.by_position" :key="pos">
                <td>
                  <PosChip :pos="String(pos)" />
                  <span class="ml-2 text-muted max-tab:hidden">{{ POSITION_NAMES[pos] }}</span>
                </td>
                <td class="text-right">{{ m.rows.toLocaleString() }}</td>
                <td class="text-right font-semibold">±{{ m.model_mae.toFixed(2) }}</td>
                <td class="text-right text-muted">±{{ m.baseline_mae.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div :class="section">
        <h2 class="section-title">What the model leans on</h2>
        <div
          v-for="f in model.feature_importance"
          :key="f.feature"
          class="grid grid-cols-[minmax(120px,240px)_1fr_52px] items-center gap-3 py-1.5 text-[14px] max-tab:grid-cols-[minmax(100px,40%)_1fr_46px] max-tab:gap-2.5 max-tab:text-[13px]"
        >
          <span class="truncate">{{ featureLabel(f.feature) }}</span>
          <span class="h-2 overflow-hidden rounded-sm bg-surface-2">
            <span class="block h-full rounded-sm bg-bar" :style="{ width: `${(f.share / maxShare) * 100}%` }" />
          </span>
          <span class="text-right text-muted tabular-nums">{{ (f.share * 100).toFixed(1) }}%</span>
        </div>
      </div>

      <div :class="section">
        <h2 class="section-title">The pipeline</h2>
        <ol class="m-0 grid max-w-[780px] list-decimal gap-3 pl-[22px] leading-[1.6] marker:font-bold marker:text-accent">
          <li><strong>Data.</strong> Weekly box scores, schedules, Vegas lines, rosters and injury reports come from nflverse's free public datasets.</li>
          <li><strong>Features.</strong> For each player and week, the model only sees what was known before kickoff: recent scoring, usage (targets, carries, attempts), the team's Vegas-implied points, and how many points the opponent has allowed to that position.</li>
          <li><strong>Training.</strong> LightGBM models for PPR and standard scoring retrain each day on a small CPU job; half-PPR is the average of the two. Team defenses are scored on sacks, turnovers, touchdowns, safeties, blocked kicks and points allowed.</li>
          <li><strong>Honesty check.</strong> Accuracy above comes from a model that never saw the season it was tested on. Past weeks of this season are also projected by a model trained only on earlier seasons.</li>
        </ol>
      </div>
    </template>
    <div v-else class="card mt-[18px]">
      <StateMessage kind="loading">Loading model details…</StateMessage>
    </div>
  </section>
</template>
