export type SportId = 'nba' | 'f1' | 'tennis' | 'football' | 'cricket'

export interface LeagueOption {
  id: string
  label: string
}

export interface SportOption {
  id: SportId
  label: string
  shortLabel: string
  accent: string
  leagues: LeagueOption[]
}

export interface SportContextSelection {
  sport: SportId
  league: string
  season: string
}

export const SPORT_OPTIONS: SportOption[] = [
  {
    id: 'nba',
    label: 'Basketball',
    shortLabel: 'Basketball',
    accent: '#FF6B2D',
    leagues: [
      { id: 'nba', label: 'NBA' },
      { id: 'wnba', label: 'WNBA' },
      { id: 'nbl-au', label: 'NBL (Australia)' },
      { id: 'mpbl-ph', label: 'MPBL (Philippines)' },
      { id: 'g-league', label: 'G League' },
    ],
  },
  {
    id: 'f1',
    label: 'Formula 1',
    shortLabel: 'F1',
    accent: '#FF3B4F',
    leagues: [
      { id: 'f1-world', label: 'F1 World Championship' },
      { id: 'f2', label: 'Formula 2' },
      { id: 'f3', label: 'Formula 3' },
    ],
  },
  {
    id: 'tennis',
    label: 'Tennis',
    shortLabel: 'Tennis',
    accent: '#22C55E',
    leagues: [
      { id: 'atp', label: 'ATP Tour' },
      { id: 'wta', label: 'WTA Tour' },
      { id: 'itf', label: 'ITF' },
    ],
  },
  {
    id: 'football',
    label: 'Football',
    shortLabel: 'Football',
    accent: '#38BDF8',
    leagues: [
      { id: 'epl', label: 'Premier League' },
      { id: 'laliga', label: 'La Liga' },
      { id: 'ucl', label: 'UEFA Champions League' },
    ],
  },
  {
    id: 'cricket',
    label: 'Cricket',
    shortLabel: 'Cricket',
    accent: '#F59E0B',
    leagues: [
      { id: 'ipl', label: 'IPL' },
      { id: 'bbl', label: 'BBL' },
      { id: 'icc-odi', label: 'ICC ODI' },
    ],
  },
]

export function seasonOptionsForSport(sport: SportId): string[] {
  if (sport === 'nba' || sport === 'football') {
    return ['2025-26', '2024-25', '2023-24']
  }
  return ['2026', '2025', '2024']
}

export function findSportOption(sport: SportId): SportOption {
  return SPORT_OPTIONS.find(item => item.id === sport) ?? SPORT_OPTIONS[0]
}

export function defaultLeagueForSport(sport: SportId): string {
  const option = findSportOption(sport)
  return option.leagues[0]?.id ?? 'nba'
}

export const DEFAULT_SPORT_SELECTION: SportContextSelection = {
  sport: 'nba',
  league: defaultLeagueForSport('nba'),
  season: seasonOptionsForSport('nba')[0],
}

export function isLiveDataSelection(selection: SportContextSelection): boolean {
  return selection.sport === 'nba' && selection.league === 'nba'
}
