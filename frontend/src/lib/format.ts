export const SCORING_LABELS = { ppr: 'PPR', half: 'Half', std: 'Std' } as const
export const SCORING_NAMES = { ppr: 'PPR', half: 'Half-PPR', std: 'Standard' } as const

/** A points value to fixed decimals, never shown as "-0.0". */
export function points(value: number, digits = 1): string {
  const text = value.toFixed(digits)
  return Number(text) === 0 ? (0).toFixed(digits) : text
}

/** A signed difference such as "+3.2" or "-1.4", with no sign on zero. */
export function signedPoints(value: number, digits = 1): string {
  const text = points(value, digits)
  return Number(text) > 0 ? `+${text}` : text
}

export function matchup(opponent: string, isHome: boolean | null): string {
  if (isHome === null) return opponent
  return isHome ? `vs ${opponent}` : `@ ${opponent}`
}

export function injuryClass(status: string | null): string {
  if (!status) return ''
  if (status === 'Out') return 'inj-out'
  if (status === 'Doubtful') return 'inj-doubtful'
  return 'inj-questionable'
}

export function injuryShort(status: string | null): string {
  if (!status) return ''
  return status === 'Questionable' ? 'Q' : status === 'Doubtful' ? 'D' : 'OUT'
}

export function featureLabel(feature: string): string {
  const labels: Record<string, string> = {
    ppr_last1: 'Last game',
    ppr_last3: 'Last 3 games avg',
    ppr_last5: 'Last 5 games avg',
    ppr_last10: 'Last 10 games avg',
    ppr_std5: 'Consistency (last 5)',
    std_last5: 'Non-PPR points (last 5)',
    ppr_season_avg: 'Season average',
    ppr_prev_season_avg: 'Last season average',
    implied_team_total: 'Vegas implied team total',
    opp_implied_total: 'Opponent implied total',
    team_spread: 'Point spread',
    game_total: 'Vegas game total',
    target_share_last3: 'Target share (last 3)',
    targets_last3: 'Targets (last 3)',
    receptions_last3: 'Receptions (last 3)',
    carries_last3: 'Carries (last 3)',
    attempts_last3: 'Pass attempts (last 3)',
    passing_yards_last3: 'Passing yards (last 3)',
    rushing_yards_last3: 'Rushing yards (last 3)',
    receiving_yards_last3: 'Receiving yards (last 3)',
    opp_allowed_ppr_last8: 'Opponent points allowed to position',
    opp_allowed_ppr_season: 'Opponent allowed this season',
    games_this_season: 'Games this season',
    career_games: 'Career games',
    weeks_since_last_game: 'Weeks since last game',
    position_code: 'Position',
    is_home: 'Home or away',
  }
  return labels[feature] ?? feature
}

export function relativeTime(iso: string | null, now: Date = new Date()): string {
  if (!iso) return 'never'
  const minutes = Math.round((now.getTime() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

export const POSITION_NAMES: Record<string, string> = {
  QB: 'Quarterbacks',
  RB: 'Running backs',
  WR: 'Wide receivers',
  TE: 'Tight ends',
  DST: 'Defenses',
}
