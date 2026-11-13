import { ref, watch } from 'vue'
import type { Scoring } from './api'

function readScoring(): Scoring {
  try {
    const saved = localStorage.getItem('scoring')
    if (saved === 'ppr' || saved === 'half' || saved === 'std') return saved
  } catch {
    /* storage unavailable */
  }
  return 'ppr'
}

/** The scoring format is shared across pages and remembered between visits. */
export const scoring = ref<Scoring>(readScoring())

watch(scoring, (value) => {
  try {
    localStorage.setItem('scoring', value)
  } catch {
    /* storage unavailable */
  }
})
