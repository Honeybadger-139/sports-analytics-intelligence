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

// ── Pulse — Intelligence / Brief ─────────────────────────────────────────────

export interface BriefItem {
  game_id: string
  matchup: string
  summary: string
  risk_level: 'low' | 'medium' | 'high'
  citation_count: number
}

export interface DailyBriefResponse {
  date: string
  season: string
  items: BriefItem[]
}

// ── Pulse — Match Previews ────────────────────────────────────────────────────

export interface MatchRow {
  game_id: string
  game_date: string
  season: string
  home_team: string
  away_team: string
  home_score: number | null
  away_score: number | null
  winner_team_id: number | null
}

export interface MatchesResponse {
  matches: MatchRow[]
  count: number
}

export interface TodayGamePrediction {
  game_id: string
  home_team: string
  away_team: string
  home_team_name?: string
  away_team_name?: string
  game_date?: string
  predictions?: Record<string, { home_win_prob: number; away_win_prob: number; confidence: number }>
  [key: string]: unknown
}

export interface TodayPredictionsResponse {
  date: string
  count: number
  persisted_rows: number
  games: TodayGamePrediction[]
}

// ── Pulse — Game Stats (Box Score Modal) ─────────────────────────────────────

export interface TeamBoxScore {
  team_id: number
  team: string
  team_name: string
  points: number
  rebounds: number
  assists: number
  steals: number
  blocks: number
  turnovers: number
  field_goal_pct: number | null
  three_point_pct: number | null
  free_throw_pct: number | null
  offensive_rating: number | null
  defensive_rating: number | null
  pace: number | null
  effective_fg_pct: number | null
  true_shooting_pct: number | null
}

export interface PlayerBoxScore {
  player_id: number
  player_name: string
  team: string
  team_id: number
  minutes: string | null
  points: number
  rebounds: number
  assists: number
  steals: number
  blocks: number
  turnovers: number
  personal_fouls: number
  field_goals_made: number
  field_goals_attempted: number
  field_goal_pct: number | null
  three_points_made: number
  three_points_attempted: number
  three_point_pct: number | null
  free_throws_made: number
  free_throws_attempted: number
  free_throw_pct: number | null
  plus_minus: number | null
  fantasy_points: string | null
}

export interface GameStatsResponse {
  game_id: string
  game_date: string
  season: string
  home_team: string
  home_team_name: string
  away_team: string
  away_team_name: string
  home_score: number | null
  away_score: number | null
  winner_team_id: number | null
  team_stats: {
    home: TeamBoxScore | null
    away: TeamBoxScore | null
  }
  player_stats: {
    home: PlayerBoxScore[]
    away: PlayerBoxScore[]
  }
}

// ── Arena ─────────────────────────────────────────────────────────────────────

export interface ModelPrediction {
  home_win_prob: number
  away_win_prob: number
  confidence: number
}

export interface ShapFactor {
  feature: string
  shap_value: number
  display_name?: string
}

export interface GamePredictionResponse {
  game_id: string
  home_team: string
  away_team: string
  home_team_name: string
  away_team_name: string
  predictions: Record<string, ModelPrediction>
  explanation: Record<string, ShapFactor[]>
}

export interface ModelPerformanceItem {
  model_name: string
  evaluated_games: number
  correct_games: number
  accuracy: number
  avg_confidence: number
  brier_score: number
  first_prediction_at: string | null
  last_prediction_at: string | null
}

export interface ModelPerformanceResponse {
  season: string
  model_filter: string | null
  pending_games: number
  evaluated_models: number
  performance: ModelPerformanceItem[]
}

// ── Deep Dive — Player & Team Stats ──────────────────────────────────────────

export interface PlayerListItem {
  player_id: number
  full_name: string
  is_active: boolean
  team_abbreviation: string | null
  team_name: string | null
}

export interface PlayersListResponse {
  players: PlayerListItem[]
  count: number
}

export interface PlayerGameLogEntry {
  game_id: string
  game_date: string
  season: string
  team: string
  opponent: string
  location: string
  result: string | null
  minutes: string | null
  points: number
  rebounds: number
  assists: number
  steals: number
  blocks: number
  turnovers: number
  personal_fouls: number
  field_goals_made: number
  field_goals_attempted: number
  field_goal_pct: number | null
  three_points_made: number
  three_points_attempted: number
  three_point_pct: number | null
  free_throws_made: number
  free_throws_attempted: number
  free_throw_pct: number | null
  plus_minus: number | null
  fantasy_points: string | null
}

export interface PlayerGameLogResponse {
  player: PlayerListItem
  season: string
  averages: Record<string, number>
  games: PlayerGameLogEntry[]
}

export interface TeamInfo {
  team_id: number
  abbreviation: string
  full_name: string
  city: string
}

export interface TeamGameLogEntry {
  game_id: string
  game_date: string
  season: string
  opponent: string
  location: string
  result: string | null
  points: number
  opponent_points: number | null
  rebounds: number
  assists: number
  steals: number
  blocks: number
  turnovers: number
  field_goal_pct: number | null
  three_point_pct: number | null
  free_throw_pct: number | null
  offensive_rating: number | null
  defensive_rating: number | null
  pace: number | null
  effective_fg_pct: number | null
  true_shooting_pct: number | null
}

export interface TeamGameLogResponse {
  team: TeamInfo
  season: string
  record: { wins: number; losses: number; games: number }
  games: TeamGameLogEntry[]
}
