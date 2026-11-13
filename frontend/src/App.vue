<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { scoring } from './lib/store'
import { SCORING_LABELS } from './lib/format'
import type { Scoring } from './lib/api'

const formats = Object.entries(SCORING_LABELS) as [Scoring, string][]
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <RouterLink to="/" class="brand">
        <span class="brand-mark" aria-hidden="true">FP</span>
        <span class="brand-name">Fantasy Score Predictor</span>
      </RouterLink>
      <nav class="nav">
        <RouterLink to="/" class="nav-link" exact-active-class="active">Projections</RouterLink>
        <RouterLink to="/about" class="nav-link" active-class="active">How it works</RouterLink>
      </nav>
      <div class="segmented" role="radiogroup" aria-label="Scoring format">
        <button
          v-for="[value, label] in formats"
          :key="value"
          type="button"
          role="radio"
          :aria-checked="scoring === value"
          :class="{ on: scoring === value }"
          @click="scoring = value"
        >
          {{ label }}
        </button>
      </div>
    </div>
  </header>
  <main class="page">
    <RouterView />
  </main>
  <footer class="footer">
    Data from <a href="https://github.com/nflverse" target="_blank" rel="noopener">nflverse</a>. Projections are
    estimates, not guarantees.
  </footer>
</template>
