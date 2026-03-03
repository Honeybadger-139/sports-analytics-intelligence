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
  session_id?: string
}

export interface ChatResponse {
  reply: string
}

// ── Scribble ─────────────────────────────────────────────────────────────────

export interface RawTableMeta {
  table: string
  label: string
  description: string
  season_filter_supported: boolean
  row_count: number
}

export interface TableListResponse {
  season: string
  tables: RawTableMeta[]
}

export interface TableRowsResponse {
  table: string
  season: string | null
  limit: number
  offset: number
  total: number
  rows: Record<string, unknown>[]
}

export interface SqlQueryRequest {
  sql: string
}

export interface SqlQueryResponse {
  sql: string
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  elapsed_ms: number
}

export interface SavedNotebook {
  id: string
  name: string
  description: string
  sql: string
  savedAt: string
  updatedAt?: string
}

export interface ScribbleView {
  name: string
  description: string
  sql: string
  created_at: string
}

export interface ViewCreateRequest {
  name: string
  description: string
  sql: string
}

// ── Lab — Data Quality ────────────────────────────────────────────────────────

export interface PipelineRun {
  sync_time: string
  module: string
  status: string
  records_processed: number
  records_inserted: number
  errors: string | null
  elapsed_seconds: number | null
}

export interface TopTeam {
  abbreviation: string
  games_played: number
  wins: number
  losses: number
  win_pct: number
}

export interface QualityOverview {
  season: string
  row_counts: {
    matches: number
    teams: number
    players: number
    team_game_stats: number
    player_game_stats: number
  }
  quality_checks: Record<string, unknown>
  pipeline_timing: {
    avg_ingestion_seconds: number | null
    avg_feature_seconds: number | null
    latest_ingestion_seconds: number | null
    latest_feature_seconds: number | null
  }
  top_teams: TopTeam[]
  recent_runs: PipelineRun[]
}

// ── Lab — MLOps ───────────────────────────────────────────────────────────────

export interface MLOpsAlert {
  type: string
  message: string
  level: string
}

export interface MLOpsMonitoringOverview {
  season: string
  evaluated_predictions: number
  accuracy: number | null
  brier_score: number | null
  accuracy_threshold: number
  brier_threshold: number
  game_data_freshness_days: number | null
  pipeline_freshness_days: number | null
  alerts: MLOpsAlert[]
  alert_count: number
  escalation_level: string
  recommended_action: string
  breach_streak: number
}

export interface MLOpsTrendPoint {
  snapshot_time: string
  accuracy: number | null
  brier_score: number | null
  alert_count: number
}

export interface MLOpsMonitoringTrend {
  season: string
  days: number
  points: MLOpsTrendPoint[]
}

export interface RetrainPolicyResult {
  season: string
  dry_run: boolean
  should_retrain: boolean
  reasons: string[]
  accuracy: number | null
  brier_score: number | null
  new_labels_since_last_train: number
  thresholds: Record<string, unknown>
}

export interface RetrainJob {
  id: number
  season: string
  status: string
  trigger_source: string
  reasons: string[] | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  error: string | null
}

export interface RetrainJobsResponse {
  season: string
  jobs: RetrainJob[]
}
