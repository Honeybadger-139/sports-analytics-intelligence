# 2026-03-07 - Grafana curated dashboards provisioning

## Type
Feature enablement (reporting add-on)

## Goal
Provide immediately useful dashboards in Grafana after login, without manual dashboard setup.

## What changed
- Added Grafana provisioning assets:
  - `grafana/provisioning/datasources/postgres.yml`
  - `grafana/provisioning/dashboards/dashboards.yml`
- Added curated dashboards:
  - `grafana/dashboards/gamethread-league-overview.json`
  - `grafana/dashboards/gamethread-team-player-trends.json`
- Updated Grafana compose mounts:
  - `docker-compose.yml`
  - mounted provisioning subfolders + dashboards directory
- Updated docs:
  - `README.md`
  - `docs/learning-notes/frontend/README.md`
  - `docs/learning-notes/README.md`

## Provisioned content
- Datasource: `GameThread Postgres` (UID: `gamethread-pg`)
- Folder: `GameThread`
- Dashboards:
  - `GameThread - League Overview`
  - `GameThread - Team & Player Trends`

## Validation
- `docker-compose up -d grafana` ✅
- `curl -sS -I http://127.0.0.1:3301/ | head -n 1` → `HTTP/1.1 302 Found` ✅
- Grafana logs show dashboard index with `size=2` and provisioning completion ✅

## Linear
- Issue: `SCR-216`
