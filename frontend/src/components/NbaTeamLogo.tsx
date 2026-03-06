import { useEffect, useMemo, useState } from 'react'
import { getNbaTeamLogoUrl, resolveNbaTeamAbbreviation } from '../utils/nbaTeams'

interface NbaTeamLogoProps {
  team: string | number | null | undefined
  altLabel?: string
  size?: number
}

function fallbackText(label: string): string {
  const trimmed = label.trim()
  if (!trimmed) return '?'
  const words = trimmed.split(/\s+/).filter(Boolean)
  if (words.length >= 2) {
    return `${words[0][0] ?? ''}${words[1][0] ?? ''}`.toUpperCase()
  }
  return trimmed.slice(0, 3).toUpperCase()
}

export default function NbaTeamLogo({ team, altLabel, size = 26 }: NbaTeamLogoProps) {
  const logoUrl = useMemo(() => getNbaTeamLogoUrl(team), [team])
  const abbr = useMemo(() => resolveNbaTeamAbbreviation(team), [team])
  const fallback = useMemo(
    () => fallbackText(altLabel ?? abbr ?? (team == null ? '' : String(team))),
    [abbr, altLabel, team],
  )
  const [errored, setErrored] = useState(false)

  useEffect(() => {
    setErrored(false)
  }, [logoUrl])

  return (
    <span
      aria-label={`${altLabel ?? abbr ?? fallback} logo`}
      title={altLabel ?? abbr ?? fallback}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        border: '1px solid var(--border)',
        background: 'var(--bg-elevated)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        flexShrink: 0,
      }}
    >
      {logoUrl && !errored ? (
        <img
          src={logoUrl}
          alt={`${altLabel ?? abbr ?? fallback} logo`}
          onError={() => setErrored(true)}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        />
      ) : (
        <span style={{ fontSize: Math.max(10, Math.floor(size * 0.34)), color: 'var(--text-2)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
          {fallback}
        </span>
      )}
    </span>
  )
}
