/**
 * TimezoneContext
 *
 * All game dates in this app are stored in US/Eastern (ET) time — the NBA's
 * official game-date timezone (see backend/src/data/espn_transformer.py for
 * the full rationale).
 *
 * This context lets users toggle between ET (as stored) and IST (UTC+5:30)
 * display.  Because we only store the calendar date (not exact tip-off time),
 * the IST conversion adds +1 day to every date — a practical approximation
 * since virtually all NBA games tip off in the evening ET, which rolls into
 * the next calendar day in IST.
 *
 * Preference is persisted to localStorage under "tz_pref".
 */

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

type TzPref = 'ET' | 'IST'

interface TimezoneCtx {
  tz: TzPref
  toggle: () => void
  /** Format a YYYY-MM-DD string according to the active timezone preference */
  fmtDate: (iso: string | null | undefined) => string
}

const TimezoneContext = createContext<TimezoneCtx | null>(null)

const STORAGE_KEY = 'tz_pref'

function parseSavedTz(): TzPref {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'IST' ? 'IST' : 'ET'
  } catch {
    return 'ET'
  }
}

/**
 * Convert a YYYY-MM-DD date string for display.
 *
 * ET mode  → show the stored date as-is (NBA official date).
 * IST mode → add 1 calendar day (NBA evening games cross midnight into IST
 *             next day).  Early afternoon games (<~6:30 AM IST) would be on
 *             the same IST day, but those are rare; +1 is the right heuristic
 *             for the vast majority of the schedule.
 */
export function formatDateTz(iso: string | null | undefined, tz: TzPref): string {
  if (!iso) return '—'
  try {
    // Parse as local noon to avoid any UTC-offset date shifting
    const [y, m, d] = iso.split('-').map(Number)
    const date = new Date(y, m - 1, d, 12, 0, 0)
    if (tz === 'IST') {
      date.setDate(date.getDate() + 1)
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return iso
  }
}

export function TimezoneProvider({ children }: { children: ReactNode }) {
  const [tz, setTz] = useState<TzPref>(parseSavedTz)

  const toggle = useCallback(() => {
    setTz(prev => {
      const next: TzPref = prev === 'ET' ? 'IST' : 'ET'
      try { localStorage.setItem(STORAGE_KEY, next) } catch { /* ignore */ }
      return next
    })
  }, [])

  const fmtDate = useCallback(
    (iso: string | null | undefined) => formatDateTz(iso, tz),
    [tz],
  )

  return (
    <TimezoneContext.Provider value={{ tz, toggle, fmtDate }}>
      {children}
    </TimezoneContext.Provider>
  )
}

export function useTimezone(): TimezoneCtx {
  const ctx = useContext(TimezoneContext)
  if (!ctx) throw new Error('useTimezone must be used inside <TimezoneProvider>')
  return ctx
}
