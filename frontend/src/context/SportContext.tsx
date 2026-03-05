import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  DEFAULT_SPORT_SELECTION,
  SPORT_OPTIONS,
  defaultLeagueForSport,
  findSportOption,
  seasonOptionsForSport,
  type SportContextSelection,
  type SportId,
} from '../config/sports'

const STORAGE_KEY = 'sai_global_sport_context_v1'

interface SportContextValue {
  selection: SportContextSelection
  sportOptions: typeof SPORT_OPTIONS
  leagueOptions: Array<{ id: string; label: string }>
  seasonOptions: string[]
  setSport: (sport: SportId) => void
  setLeague: (league: string) => void
  setSeason: (season: string) => void
}

const SportContext = createContext<SportContextValue | null>(null)

function readStoredSelection(): SportContextSelection {
  if (typeof window === 'undefined') return DEFAULT_SPORT_SELECTION

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SPORT_SELECTION

    const parsed = JSON.parse(raw) as Partial<SportContextSelection>
    const sport = parsed.sport ?? DEFAULT_SPORT_SELECTION.sport
    const league = parsed.league ?? defaultLeagueForSport(sport)
    const seasonCandidates = seasonOptionsForSport(sport)
    const season = seasonCandidates.includes(parsed.season ?? '') ? (parsed.season as string) : seasonCandidates[0]
    return { sport, league, season }
  } catch {
    return DEFAULT_SPORT_SELECTION
  }
}

export function SportContextProvider({ children }: { children: ReactNode }) {
  const [selection, setSelection] = useState<SportContextSelection>(() => readStoredSelection())

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(selection))
  }, [selection])

  const leagueOptions = useMemo(() => findSportOption(selection.sport).leagues, [selection.sport])
  const seasonOptions = useMemo(() => seasonOptionsForSport(selection.sport), [selection.sport])

  const value = useMemo<SportContextValue>(() => {
    return {
      selection,
      sportOptions: SPORT_OPTIONS,
      leagueOptions,
      seasonOptions,
      setSport: (sport: SportId) => {
        const nextLeagues = findSportOption(sport).leagues
        const nextLeague = nextLeagues[0]?.id ?? defaultLeagueForSport(sport)
        const nextSeasons = seasonOptionsForSport(sport)
        setSelection({
          sport,
          league: nextLeague,
          season: nextSeasons[0],
        })
      },
      setLeague: (league: string) => {
        const valid = leagueOptions.some(item => item.id === league)
        setSelection(prev => ({
          ...prev,
          league: valid ? league : leagueOptions[0]?.id ?? prev.league,
        }))
      },
      setSeason: (season: string) => {
        const valid = seasonOptions.includes(season)
        setSelection(prev => ({
          ...prev,
          season: valid ? season : seasonOptions[0] ?? prev.season,
        }))
      },
    }
  }, [leagueOptions, seasonOptions, selection])

  return <SportContext.Provider value={value}>{children}</SportContext.Provider>
}

export function useSportContext() {
  const ctx = useContext(SportContext)
  if (!ctx) throw new Error('useSportContext must be used inside SportContextProvider')
  return ctx
}
