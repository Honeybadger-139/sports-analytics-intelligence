export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'error'
  database: string
  pipeline: {
    last_status: string
    last_sync: string | null
  }
  stats: {
    matches: number
    features: number
    active_players: number
  }
  audit_history: AuditRow[]
}

export interface AuditRow {
  sync_time: string
  module: string
  status: string
  processed?: number
  records_processed?: number
  inserted?: number
  records_inserted?: number
  details?: { elapsed_seconds?: number }
  errors?: string
}

export interface BankrollSummary {
  season: string
  total_bets: number
  settled_bets: number
  total_stake: number
  total_pnl: number
  current_bankroll: number
  roi: number
  open_bets: number
}

export interface NavSubItem {
  label: string
  path: string
  description: string
}

export interface NavItem {
  id: string
  label: string
  path: string
  description: string
  color: string
  subItems: NavSubItem[]
  badge?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  timestamp: string
}

export interface ChatRequest {
  message: string
  history: Array<{ role: 'user' | 'assistant'; content: string }>
}

export interface ChatResponse {
  reply: string
}
