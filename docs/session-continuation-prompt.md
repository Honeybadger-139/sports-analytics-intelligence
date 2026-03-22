# Session Continuation Prompt — Sports Analytics Intelligence Platform
> Generated: 2026-03-21 | Use this to resume work in a new session

---

## Project: Sports Analytics Intelligence Platform (GameThread)

**Repository**: `sports-analytics-intelligence` (GitHub)
**Linear Team**: Personal | **Project**: Sports Analytics Intelligence Platform
**GCP Project**: `sports-analytics-intelligence` | **Region**: `us-central1`
**Current Branch**: `main` (latest commit: `2396a40`)

---

## What Has Been Completed (Phases 1–5 + GCP Deployment)

### Phase 1 — Data Foundation & ML Engine
- **Data Ingestion**: `backend/src/data/ingestion.py` — idempotent upsert pipeline pulling NBA data (teams, game logs, players, player game logs, player season stats) with retry + exponential backoff + jittered rate limiting
- **Database Schema**: PostgreSQL tables: `teams`, `matches`, `team_game_stats`, `players`, `player_game_stats`, `player_season_stats`, `match_features`, `pipeline_audit`
- **Feature Engineering**: SQL-based feature store (`feature_store.py`) with rolling stats, H2H metrics, home/away splits, rest-day features — all computed via PostgreSQL window functions
- **ML Models**: XGBoost + LightGBM ensemble, SHAP explanations, Kelly Criterion bet sizing
- **Prediction Serving**: `/api/v1/predictions/today` (batch) + `/api/v1/predictions/performance` (evaluation)
- **Domain-aware imputation**, pre-feature validation gate, ONNX export, library version pinning

### Phase 2 — GCP Infrastructure
- **Cloud Run Service**: API serving (FastAPI + Gunicorn/UvicornWorker)
- **Cloud Run Job**: `job-nba-raw-ingestion` for batch ingestion
- **Cloud SQL**: PostgreSQL instance
- **GCS Bucket**: `gamethread-raw` for Parquet snapshots after ingestion
- **Pub/Sub**: `pipeline-events` topic for completion events
- **Secret Manager**: DATABASE_URL, GCS_RAW_BUCKET, PUBSUB_PIPELINE_TOPIC
- **Artifact Registry**: `us-central1-docker.pkg.dev/sports-analytics-intelligence/gamethread/`
- **Cloud Build**: Used for Docker builds (bypasses broken Cloud Shell Docker credential helper)
- **Split health probes**: `/healthz` (liveness) + `/readyz` (readiness)

### Phase 3 — Orchestration
- **Pub/Sub → Prefect bridge** designed and coded (`prefect_agent.py`, `deploy_flow.py`, `pubsub_trigger.py`)
- **DEFERRED**: Prefect Cloud free plan blocks hybrid/push work pools (403). Architecture is correct; requires Prefect Pro or self-hosted Prefect server to activate. All code exists, just not executing.

### Phase 4 — MLOps
- **Vertex AI Experiments** for training run tracking
- **Vertex Model Registry** with alias-based promotion (production/staging/champion)
- **Vertex AI Pipelines** for governed retrain workflow
- **Drift detection**: KL divergence on prediction distributions (threshold > 0.1)
- **Retrain policy APIs**: `/api/v1/mlops/monitoring`, `/api/v1/mlops/retrain/policy`

### Phase 5 — Monitoring & Dashboards
- **Cloud Monitoring** custom metrics: `prediction_confidence`, `data_freshness_hours`, `model_accuracy`, `feature_null_rate`
- **Looker Studio** dashboard specs for operational visibility
- **Alert policies** for ML-specific health signals

### Frontend (React)
- **Pages**: Overview, Pulse, Arena, Lab, Dashboard, Scribble (SQL workspace), Chatbot
- **Sport context gating**: NBA live, others "Coming Soon"
- **Chatbot**: Dual-engine (legacy + LangGraph) with SSE streaming

### Intelligence Layer
- **RAG pipeline**: news_agent → ChromaDB vector store → Gemini LLM → citation-gated summaries
- **Graceful degradation**: deterministic fallback when LLM/vector infra unavailable
- **Citation gates**, source quality scoring, rule overlays

---

## What Was Just Completed (This Session)

### Fixed: `stats.nba.com` GCP IP Blocking

**Problem**: `ingest_season_games` used `teamgamelog.TeamGameLog` — 30 sequential API calls to `stats.nba.com`. GCP IP ranges are blocked at the application layer. TCP connections accepted but responses never sent → 60s read timeouts. Browser-like headers (User-Agent, x-nba-stats-*) did NOT bypass IP-level blocking.

**Fix Applied** (file: `backend/src/data/ingestion.py`, uncommitted):
1. **Tier 1 — LeagueGameLog**: Switched from `TeamGameLog` (30 calls) to `leaguegamelog.LeagueGameLog(player_or_team_abbreviation="T")` (1 call). Same data, 97% fewer requests, already imported.
2. **Tier 2 — balldontlie.io fallback**: New function `_ingest_games_via_balldontlie()`. Uses free `https://www.balldontlie.io/api/v1/games` API (no API key needed, not GCP-blocked). Fills `matches` table with game results/scores. Team stats (FG%, rebounds, etc.) remain NULL from this path.
3. **Graceful degradation**: If LeagueGameLog raises any exception, automatically falls back to balldontlie. Pipeline always succeeds with at least match results.

**Git status**: 1 file modified (`backend/src/data/ingestion.py`), +271 lines, -107 lines. NOT yet committed.

---

## What Needs to Happen Next (Ordered)

### Immediate — Deploy the Fix

1. **Commit the ingestion fix** to git
2. **Rebuild Docker image** using Cloud Build (Cloud Shell):
   ```bash
   cd ~/sports-analytics-intelligence/backend
   cat > /tmp/cb-ingestion.yaml << 'EOF'
   steps:
   - name: 'gcr.io/cloud-builders/docker'
     args: ['build', '-t', 'us-central1-docker.pkg.dev/sports-analytics-intelligence/gamethread/ingestion:latest', '-f', 'Dockerfile.ingestion', '.']
   images:
   - 'us-central1-docker.pkg.dev/sports-analytics-intelligence/gamethread/ingestion:latest'
   EOF
   gcloud builds submit --config /tmp/cb-ingestion.yaml --project sports-analytics-intelligence .
   ```
3. **Update Cloud Run Job**:
   ```bash
   gcloud run jobs update job-nba-raw-ingestion \
     --image us-central1-docker.pkg.dev/sports-analytics-intelligence/gamethread/ingestion:latest \
     --region us-central1 --project sports-analytics-intelligence
   ```
4. **Execute the job** and monitor:
   ```bash
   gcloud run jobs execute job-nba-raw-ingestion \
     --region us-central1 --project sports-analytics-intelligence --wait
   ```
5. **Verify data in PostgreSQL**: Check `teams` (30 rows), `matches` (should have 800+ games), `team_game_stats` (if LeagueGameLog succeeds), `player_game_stats`, `player_season_stats`

### After Ingestion Succeeds — Feature Engineering

6. **Run feature engineering** — compute `match_features` from raw data. This is normally Prefect-orchestrated but deferred (free plan limitation). Can be triggered manually or via direct Cloud Run Job.
7. **Train models** — run XGBoost + LightGBM training on computed features
8. **Generate predictions** — `/api/v1/predictions/today` for upcoming games

### Known Blockers / Open Issues

| Issue | Status | Notes |
|-------|--------|-------|
| stats.nba.com blocks GCP IPs | **Fix applied, not deployed** | LeagueGameLog + balldontlie fallback |
| Prefect Cloud free plan blocks hybrid workers | **Deferred** | Architecture correct; needs Prefect Pro or self-hosted |
| Linear workspace free issue limit reached | **Operational** | Can't create new issues until limit resets or plan upgrades |
| `team_game_stats` may be empty if stats.nba.com blocked | **Expected** | balldontlie only provides scores, not per-game team stats |

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/src/data/ingestion.py` | Main ingestion pipeline (MODIFIED — has LeagueGameLog + balldontlie fix) |
| `backend/pipeline/run_ingestion.py` | Cloud Run Job entrypoint (ingestion → GCS snapshot → Pub/Sub event) |
| `backend/src/config.py` | Central config (DATABASE_URL, REQUEST_DELAY, MAX_RETRIES, CURRENT_SEASON) |
| `backend/src/data/feature_store.py` | SQL-based feature engineering |
| `backend/src/models/trainer.py` | XGBoost/LightGBM training |
| `backend/src/models/predictor.py` | Prediction serving |
| `backend/Dockerfile.ingestion` | Docker image for ingestion job |
| `backend/requirements-pipeline.txt` | Dependencies for pipeline (includes requests, nba_api, sqlalchemy, etc.) |
| `docs/decisions/decision-log.md` | All architectural decisions (44 entries across 5 phases) |
| `docs/architecture/system-design.md` | System architecture overview |
| `docs/architecture/phase-execution-runbook.md` | Deployment runbook |

---

## Cloud Shell Authentication Notes

- **gcloud auth**: Authenticated as `2001abhigupta@gmail.com` via OAuth flow
- **Docker credential helper** is broken in Cloud Shell — always use `gcloud builds submit` instead of `docker push`
- Cloud Build service account has Artifact Registry Write permissions
- Cloud Run Job uses `--set-cloudsql-instances` (NOT `--add-cloudsql-instances`)

---

## Decision Log Entry Needed

The LeagueGameLog + balldontlie fallback decision should be added to `docs/decisions/decision-log.md` as a new Data Pipeline Decision:

**Decision**: Two-tier game ingestion — LeagueGameLog primary, balldontlie.io fallback
**Alternatives**: Keep TeamGameLog with longer timeouts, proxy/VPN, paid API (SportsRadar), scrape basketball-reference
**Why This Choice**: LeagueGameLog reduces 30 API calls to 1 (better architecture). balldontlie.io is free, cloud-friendly, and guarantees match results even when stats.nba.com is fully blocked.
**Trade-off**: Fallback path only provides game scores (no per-game FG%, rebounds, etc.) — team_game_stats columns remain NULL until stats.nba.com is reachable
**Interview Angle**: "I designed the pipeline with graceful degradation — primary source fills all stats, fallback guarantees core data always lands. This is the circuit-breaker pattern used in production data pipelines."

---

## Learning Note Needed

Create `docs/learning-notes/infrastructure/cloud-ip-blocking.md` covering:
- What: Cloud provider IPs blocked by sports data APIs
- Why: Anti-scraping measures by stats.nba.com target known cloud IP ranges
- How to handle: Alternative data sources, proxy services, graceful degradation
- Interview angle: "Understanding the operational realities of cloud-deployed data pipelines"
