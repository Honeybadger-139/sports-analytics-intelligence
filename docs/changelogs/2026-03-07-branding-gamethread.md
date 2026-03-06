# 2026-03-07 - Product branding update to GameThread

## Type
Branding refresh (no feature behavior change)

## Goal
Rename the dashboard/platform brand to a modern, concise product identity: **GameThread**.

## What changed
- Updated visible frontend branding:
  - `frontend/index.html` title + meta description
  - `frontend/src/pages/Overview.tsx` hero title
  - `frontend/src/components/SportsMark.tsx` aria label
  - `frontend/src/hooks/useChatbot.ts` welcome message
  - `frontend/src/components/Chatbot/ChatbotPanel.tsx` subtitle
- Updated backend metadata branding:
  - `backend/main.py` FastAPI app title
  - `backend/main.py` root health payload `name`
  - `backend/config/settings.yaml` app `name`
- Updated top-level documentation entry points:
  - `README.md`
  - `docs/architecture/system-design.md`
  - `docs/architecture/database-schema.md`
  - `docs/architecture/data-pipeline.md`

## Validation
- `cd frontend && npm run build` ✅
- Code-level branding verification via ripgrep across updated files (`GameThread`) ✅

## Runtime note
- Existing backend process may continue showing previous OpenAPI title until service restart.

## Linear
- Issue: `SCR-214`
