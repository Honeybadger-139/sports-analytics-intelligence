# 2026-03-07 - Grafana port remap to 3301

## Type
Environment + integration configuration update

## Goal
Avoid host port conflict with another project on `localhost:3000` by moving Grafana to `localhost:3301`.

## What changed
- Enabled Grafana service in Docker Compose:
  - `docker-compose.yml`
  - host mapping: `3301:3000`
  - container: `sports-analytics-grafana`
  - persistent volume: `grafana_data`
- Updated frontend default Grafana URL:
  - `frontend/src/utils/grafana.ts`
  - default `VITE_GRAFANA_URL` fallback now `http://localhost:3301`
- Updated environment template:
  - `.env.example`
  - `VITE_GRAFANA_URL=http://localhost:3301`
  - added optional `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`
- Updated learning docs default URL:
  - `docs/learning-notes/frontend/README.md`

## Validation
- `docker-compose up -d grafana` ✅
- `curl -sS -I http://127.0.0.1:3301/ | head -n 1` ✅ (`HTTP/1.1 302 Found`)

## Linear
- Issue: `SCR-212`
