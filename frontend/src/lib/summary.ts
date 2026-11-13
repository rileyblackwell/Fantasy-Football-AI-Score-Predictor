import { ref } from 'vue'
import { api, type Summary, type TeamInfo } from './api'

/** Site-wide summary (current week, teams, model info), fetched once and shared by every page. */
export const summary = ref<Summary | null>(null)
export const summaryError = ref('')
let pending: Promise<Summary | null> | null = null

export function loadSummary(): Promise<Summary | null> {
  if (!pending) {
    pending = api
      .summary()
      .then((s) => (summary.value = s))
      .catch((e: Error) => {
        summaryError.value = e.message
        pending = null
        return null
      })
  }
  return pending
}

export function team(abbr: string): TeamInfo | undefined {
  return summary.value?.teams?.[abbr]
}
