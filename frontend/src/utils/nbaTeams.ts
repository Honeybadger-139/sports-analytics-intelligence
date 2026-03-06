export interface NbaTeamEntry {
  id: number
  abbr: string
  names: string[]
}

const NBA_TEAMS: NbaTeamEntry[] = [
  { id: 1610612737, abbr: 'ATL', names: ['Atlanta Hawks', 'Hawks'] },
  { id: 1610612738, abbr: 'BOS', names: ['Boston Celtics', 'Celtics'] },
  { id: 1610612751, abbr: 'BKN', names: ['Brooklyn Nets', 'Nets'] },
  { id: 1610612766, abbr: 'CHA', names: ['Charlotte Hornets', 'Hornets'] },
  { id: 1610612741, abbr: 'CHI', names: ['Chicago Bulls', 'Bulls'] },
  { id: 1610612739, abbr: 'CLE', names: ['Cleveland Cavaliers', 'Cavaliers', 'Cavs'] },
  { id: 1610612742, abbr: 'DAL', names: ['Dallas Mavericks', 'Mavericks', 'Mavs'] },
  { id: 1610612743, abbr: 'DEN', names: ['Denver Nuggets', 'Nuggets'] },
  { id: 1610612765, abbr: 'DET', names: ['Detroit Pistons', 'Pistons'] },
  { id: 1610612744, abbr: 'GSW', names: ['Golden State Warriors', 'Warriors'] },
  { id: 1610612745, abbr: 'HOU', names: ['Houston Rockets', 'Rockets'] },
  { id: 1610612754, abbr: 'IND', names: ['Indiana Pacers', 'Pacers'] },
  { id: 1610612746, abbr: 'LAC', names: ['LA Clippers', 'Los Angeles Clippers', 'Clippers'] },
  { id: 1610612747, abbr: 'LAL', names: ['Los Angeles Lakers', 'Lakers'] },
  { id: 1610612763, abbr: 'MEM', names: ['Memphis Grizzlies', 'Grizzlies'] },
  { id: 1610612748, abbr: 'MIA', names: ['Miami Heat', 'Heat'] },
  { id: 1610612749, abbr: 'MIL', names: ['Milwaukee Bucks', 'Bucks'] },
  { id: 1610612750, abbr: 'MIN', names: ['Minnesota Timberwolves', 'Timberwolves', 'Wolves'] },
  { id: 1610612740, abbr: 'NOP', names: ['New Orleans Pelicans', 'Pelicans'] },
  { id: 1610612752, abbr: 'NYK', names: ['New York Knicks', 'Knicks'] },
  { id: 1610612760, abbr: 'OKC', names: ['Oklahoma City Thunder', 'Thunder'] },
  { id: 1610612753, abbr: 'ORL', names: ['Orlando Magic', 'Magic'] },
  { id: 1610612755, abbr: 'PHI', names: ['Philadelphia 76ers', '76ers', 'Sixers'] },
  { id: 1610612756, abbr: 'PHX', names: ['Phoenix Suns', 'Suns'] },
  { id: 1610612757, abbr: 'POR', names: ['Portland Trail Blazers', 'Portland Trailblazers', 'Trail Blazers', 'Blazers'] },
  { id: 1610612758, abbr: 'SAC', names: ['Sacramento Kings', 'Kings'] },
  { id: 1610612759, abbr: 'SAS', names: ['San Antonio Spurs', 'Spurs'] },
  { id: 1610612761, abbr: 'TOR', names: ['Toronto Raptors', 'Raptors'] },
  { id: 1610612762, abbr: 'UTA', names: ['Utah Jazz', 'Jazz'] },
  { id: 1610612764, abbr: 'WAS', names: ['Washington Wizards', 'Wizards'] },
]

const LEGACY_ABBR_MAP: Record<string, string> = {
  NOH: 'NOP',
  NOK: 'NOP',
  NJN: 'BKN',
  SEA: 'OKC',
  CHH: 'CHA',
  VAN: 'MEM',
}

function normalizeTeamKey(value: string): string {
  return value
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ')
}

const TEAM_ID_BY_KEY = new Map<string, number>()
const TEAM_ABBR_BY_ID = new Map<number, string>()

for (const team of NBA_TEAMS) {
  TEAM_ID_BY_KEY.set(normalizeTeamKey(team.abbr), team.id)
  TEAM_ID_BY_KEY.set(String(team.id), team.id)
  TEAM_ABBR_BY_ID.set(team.id, team.abbr)
  for (const name of team.names) {
    TEAM_ID_BY_KEY.set(normalizeTeamKey(name), team.id)
  }
}

for (const [legacy, modern] of Object.entries(LEGACY_ABBR_MAP)) {
  const id = TEAM_ID_BY_KEY.get(normalizeTeamKey(modern))
  if (id) TEAM_ID_BY_KEY.set(normalizeTeamKey(legacy), id)
}

export function resolveNbaTeamId(team: string | number | null | undefined): number | null {
  if (team == null) return null
  if (typeof team === 'number') return TEAM_ABBR_BY_ID.has(team) ? team : null
  const normalized = normalizeTeamKey(team)
  if (!normalized) return null
  return TEAM_ID_BY_KEY.get(normalized) ?? null
}

export function resolveNbaTeamAbbreviation(team: string | number | null | undefined): string | null {
  const id = resolveNbaTeamId(team)
  if (!id) return null
  return TEAM_ABBR_BY_ID.get(id) ?? null
}

export function getNbaTeamLogoUrl(team: string | number | null | undefined): string | null {
  const id = resolveNbaTeamId(team)
  if (!id) return null
  return `https://cdn.nba.com/logos/nba/${id}/global/L/logo.svg`
}
