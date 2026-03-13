# 2026-03-13 - Documentation state sync (architecture + learning notes)

## Type
Documentation accuracy and interview-readiness refresh

## Goal
Align docs with the current repository state so architecture/notes are reliable for:
- interview storytelling
- quick re-onboarding after short gaps
- implementation traceability

## What changed

### Architecture docs
- Rewrote `docs/architecture/system-design.md` to match the live React/FastAPI stack:
  - route-level frontend modules
  - sport-context gating behavior
  - intelligence/chat (LangGraph + SSE) flow
  - scheduler + ops table observability loop
- Updated `docs/architecture/data-pipeline.md`:
  - current scheduled job model
  - bootstrap behavior for empty prediction-performance history
  - clearer ingestion/feature/intelligence linkage
- Updated `docs/architecture/database-schema.md`:
  - table grouping by raw/model/ops/workspace concerns
  - explicit operational governance tables
- Added a current-state note at the top of `docs/architecture/phase-execution-runbook.md`.

### Notes and study docs
- Updated `docs/README.md` structure + start order to reflect current docs priorities.
- Rewrote `docs/learning-notes/README.md` baseline snapshot and study order.
- Added `docs/learning-notes/interview-2-day-refresh.md` for fast recall.
- Rewrote `docs/learning-notes/frontend/README.md` around current React production architecture.
- Rewrote `docs/learning-notes/api-layer/README.md` with complete route families (including Scribble notebooks/views/ai-sql and chat streaming).
- Updated status headers in:
  - `docs/learning-notes/frontend/ui-redesign.md`
  - `docs/learning-notes/frontend/chatbot-ui.md`
  - `docs/learning-notes/frontend/scribble-playground.md`
- Refreshed `docs/learning-notes/future-learning-roadmap.md` to remove stale branch-era milestones and focus on next practical learning levels.

## Validation
- Manual consistency pass against current code paths in:
  - `frontend/src/App.tsx`
  - `frontend/src/config/sports.ts`
  - `backend/src/api/*.py`
  - `backend/src/config.py`
  - `backend/scheduler.py`
- Verified docs compile as plain Markdown and internal relative links resolve.

## Linear
- Issue: `SCR-282`
