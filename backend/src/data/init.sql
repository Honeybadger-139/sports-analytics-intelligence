-- =====================================================
-- Sports Analytics Intelligence Platform
-- Database Initialization Script
-- =====================================================

-- Teams table: stores NBA team information
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    team_id INTEGER UNIQUE NOT NULL,          -- NBA API team ID
    abbreviation VARCHAR(10) NOT NULL,         -- e.g., 'LAL', 'BOS'
    full_name VARCHAR(100) NOT NULL,           -- e.g., 'Los Angeles Lakers'
    city VARCHAR(50),
    conference VARCHAR(10),                    -- East / West
    division VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Players table: stores player info and status
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    player_id INTEGER UNIQUE NOT NULL,         -- NBA API player ID
    full_name VARCHAR(100) NOT NULL,
    team_id INTEGER REFERENCES teams(team_id),
    position VARCHAR(10),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Matches table: stores game results
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) UNIQUE NOT NULL,       -- NBA API game ID
    game_date DATE NOT NULL,
    season VARCHAR(10) NOT NULL,               -- e.g., '2025-26'
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    winner_team_id INTEGER REFERENCES teams(team_id),
    is_completed BOOLEAN DEFAULT FALSE,
    venue VARCHAR(100),
    attendance INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Team game stats: per-game team performance metrics
CREATE TABLE IF NOT EXISTS team_game_stats (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) REFERENCES matches(game_id),
    team_id INTEGER REFERENCES teams(team_id),
    points INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    steals INTEGER,
    blocks INTEGER,
    turnovers INTEGER,
    field_goal_pct DECIMAL(5,3),
    three_point_pct DECIMAL(5,3),
    free_throw_pct DECIMAL(5,3),
    offensive_rating DECIMAL(6,2),
    defensive_rating DECIMAL(6,2),
    pace DECIMAL(6,2),
    effective_fg_pct DECIMAL(5,3),
    true_shooting_pct DECIMAL(5,3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (game_id, team_id)
);

-- Computed features: pre-calculated features for ML models
CREATE TABLE IF NOT EXISTS match_features (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) REFERENCES matches(game_id),
    team_id INTEGER REFERENCES teams(team_id),
    -- Rolling form features
    win_pct_last_5 DECIMAL(5,3),
    win_pct_last_10 DECIMAL(5,3),
    avg_point_diff_last_5 DECIMAL(6,2),
    avg_point_diff_last_10 DECIMAL(6,2),
    -- Head-to-head features
    h2h_win_pct DECIMAL(5,3),
    h2h_avg_margin DECIMAL(6,2),
    -- Rest and schedule
    days_rest INTEGER,
    is_back_to_back BOOLEAN DEFAULT FALSE,
    is_home BOOLEAN,
    -- Advanced metrics (rolling)
    avg_off_rating_last_5 DECIMAL(6,2),
    avg_def_rating_last_5 DECIMAL(6,2),
    avg_pace_last_5 DECIMAL(6,2),
    avg_efg_last_5 DECIMAL(5,3),
    -- Streak info
    current_streak INTEGER,                    -- positive = win streak, negative = loss streak
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (game_id, team_id)
);

-- Predictions: model predictions for matches
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) REFERENCES matches(game_id),
    model_name VARCHAR(50) NOT NULL,           -- e.g., 'xgboost_v1', 'ensemble_v1'
    home_win_prob DECIMAL(5,4),
    away_win_prob DECIMAL(5,4),
    confidence DECIMAL(5,4),
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Actual result (filled after game)
    was_correct BOOLEAN,
    UNIQUE (game_id, model_name)
);

-- Bets: tracking placed bets and outcomes
CREATE TABLE IF NOT EXISTS bets (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(20) REFERENCES matches(game_id),
    bet_type VARCHAR(50) NOT NULL,             -- 'match_winner', 'over_under', 'quarter', etc.
    selection VARCHAR(100) NOT NULL,           -- what was bet on
    odds DECIMAL(8,4) NOT NULL,
    stake DECIMAL(10,2) NOT NULL,
    kelly_fraction DECIMAL(5,4),               -- what Kelly recommended
    model_probability DECIMAL(5,4),            -- model's estimated probability
    result VARCHAR(20),                        -- 'win', 'loss', 'push', 'pending'
    pnl DECIMAL(10,2),                         -- profit/loss
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP
);

-- Bankroll: daily bankroll snapshots
CREATE TABLE IF NOT EXISTS bankroll (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    opening_balance DECIMAL(12,2),
    closing_balance DECIMAL(12,2),
    daily_pnl DECIMAL(10,2),
    bets_placed INTEGER DEFAULT 0,
    bets_won INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for frequent queries
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(game_date);
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season);
CREATE INDEX IF NOT EXISTS idx_team_stats_game ON team_game_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_features_game ON match_features(game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_bets_game ON bets(game_id);
CREATE INDEX IF NOT EXISTS idx_bets_result ON bets(result);
