<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type Summary } from '../lib/api'
import { featureLabel, relativeTime } from '../lib/format'

const summary = ref<Summary | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    summary.value = await api.summary()
  } catch (e) {
    error.value = (e as Error).message
  }
})

const model = computed(() => summary.value?.model ?? null)
const metrics = computed(() => model.value?.metrics ?? {})
const improvement = computed(() => {
  const m = metrics.value
  if (!m.model_mae || !m.baseline_mae) return null
  return ((1 - m.model_mae / m.baseline_mae) * 100).toFixed(1)
})
const maxShare = computed(() => Math.max(0.01, ...(model.value?.feature_importance ?? []).map((f) => f.share)))
</script>

<template>
  <section>
    <h1>How the projections work</h1>
    <p class="subtitle">A gradient-boosted model trained on every regular-season game since 2016.</p>

    <div v-if="error" class="card state">Couldn't load model details: {{ error }}</div>
    <template v-else-if="model">
      <div class="stats-row">
        <div class="card stat">
          <div class="stat-label">Average miss (PPR points)</div>
          <div class="stat-value">±{{ metrics.model_mae?.toFixed(2) ?? '–' }}</div>
          <div class="meta">Tested on the full {{ metrics.holdout_season }} season</div>
        </div>
        <div class="card stat">
          <div class="stat-label">Better than season average</div>
          <div class="stat-value">{{ improvement !== null ? `${improvement}%` : '–' }}</div>
          <div class="meta">Baseline misses by ±{{ metrics.baseline_mae?.toFixed(2) }}</div>
        </div>
        <div class="card stat">
          <div class="stat-label">Training games</div>
          <div class="stat-value">{{ model.training_rows.toLocaleString() }}</div>
          <div class="meta">Trained in {{ model.training_seconds }}s, {{ relativeTime(model.trained_at) }}</div>
        </div>
      </div>

      <div class="card section">
        <h2>Accuracy by position</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Position</th>
                <th class="num">Games tested</th>
                <th class="num">Model miss</th>
                <th class="num">Season-average miss</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, pos) in metrics.by_position" :key="pos">
                <td><span class="pos">{{ pos }}</span></td>
                <td class="num">{{ m.rows.toLocaleString() }}</td>
                <td class="num" style="font-weight: 600">±{{ m.model_mae.toFixed(2) }}</td>
                <td class="num muted">±{{ m.baseline_mae.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card section">
        <h2>What the model leans on</h2>
        <div v-for="f in model.feature_importance" :key="f.feature" class="feature">
          <span class="feature-name">{{ featureLabel(f.feature) }}</span>
          <span class="feature-bar"><span :style="{ width: `${(f.share / maxShare) * 100}%` }" /></span>
          <span class="feature-share">{{ (f.share * 100).toFixed(1) }}%</span>
        </div>
      </div>

      <div class="card section">
        <h2>The pipeline</h2>
        <ol class="steps">
          <li><strong>Data.</strong> Weekly box scores, schedules, Vegas lines, rosters and injury reports come from nflverse's free public datasets.</li>
          <li><strong>Features.</strong> For each player and week, the model only sees what was known before kickoff: recent scoring, usage (targets, carries, attempts), the team's Vegas-implied points, and how many points the opponent has allowed to that position.</li>
          <li><strong>Training.</strong> LightGBM models for PPR and standard scoring retrain each day on a small CPU job; half-PPR is the average of the two.</li>
          <li><strong>Honesty check.</strong> Accuracy above comes from a model that never saw the season it was tested on. Past weeks of this season are also projected by a model trained only on earlier seasons.</li>
        </ol>
      </div>
    </template>
    <div v-else class="card state">Loading…</div>
  </section>
</template>

<style scoped>
.feature {
  display: grid;
  grid-template-columns: minmax(120px, 240px) 1fr 52px;
  gap: 12px;
  align-items: center;
  padding: 5px 0;
  font-size: 14px;
}
.feature-bar {
  height: 8px;
  background: var(--surface-2);
  border-radius: 4px;
  overflow: hidden;
}
.feature-bar span {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: 4px;
}
.feature-share {
  text-align: right;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.steps {
  margin: 0;
  padding-left: 20px;
  display: grid;
  gap: 8px;
}
</style>
