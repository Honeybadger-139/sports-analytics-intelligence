# Future Learning Roadmap

This roadmap captures next learning priorities after Phase 0 hardening and Phase 1 reliability completion.

## Current Baseline (Done)

1. Structured ingestion resilience (rate limiting, retries, idempotent upserts).
2. Feature reliability hardening (H2H execution + non-leaky pregame streaks).
3. Advanced metric completeness with targeted backfill.
4. Self-healing observability bootstrap for legacy DB volumes.

## Level 1: Immediate (Interview-Ready on Existing System)

1. Data quality contracts and API exposure design.
2. DB-backed integration testing patterns for ingestion pipelines.
3. FastAPI route contract testing (including failure-mode behavior).
4. Practical logging and rotation policy design.
5. Feature leakage case studies (what breaks if ordering/lag is wrong).

## Level 2: Near-Term (Phase 2 Readiness)

1. Prediction persistence design (`predictions` table as audit source of truth).
2. Outcome reconciliation design (`was_correct`, delayed label updates).
3. Model-performance API contracts (accuracy, calibration, Brier over time).
4. Bankroll ledger design fundamentals (`bets` lifecycle and PnL accounting).
5. Migration/versioning strategies for schema + feature contracts.

## Level 3: Production Readiness (Phase 3/4 Transition)

1. CI/CD test gate design for data + API + model layers.
2. Runtime parity and dependency control (local/CI/prod).
3. Alerting strategy from audit tables (freshness, failure rate, anomalies).
4. Feature-store governance (lineage, reproducibility, controlled backfills).
5. Model monitoring fundamentals (drift, calibration, performance decay).

## Level 4: Advanced Platform Skills

1. Experiment tracking and reproducible model packaging.
2. Multi-source ingestion resilience (fallback providers, replay pipelines).
3. RAG evaluation methodology for Intelligence Layer quality.
4. Rule-engine governance (deterministic overrides, auditability, explainability).

## Recommended Study Flow

1. Master Level 1 before implementing large new feature surfaces.
2. Pair Level 2 with Phase 2 implementation tasks.
3. Execute Level 3 during Phase 3/4 to avoid operational debt.
4. Use Level 4 to prepare for senior/architect interview scenarios.
