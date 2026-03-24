#!/usr/bin/env bash
# ============================================================================
# start-local-tunnel.sh — Start local API + ngrok tunnel for Composer DAG
# ============================================================================
# Run this BEFORE any Airflow DAG trigger.
# Keeps your laptop's residential IP as the NBA API egress point.
#
# Usage:
#   cd /path/to/sports-analytics-intelligence
#   ./infra/composer/start-local-tunnel.sh
# ============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
PROXY_BINARY="$REPO_ROOT/cloud-sql-proxy"
CLOUD_SQL_INSTANCE="sports-analytics-intelligence:us-central1:sports-analytics-pg"
PROXY_PORT=5434
API_PORT=8000
NGROK_PORT=4040
COMPOSER_ENV="gamethread-composer"
COMPOSER_REGION="us-central1"
COMPOSER_PROJECT="sports-analytics-intelligence"

cd "$REPO_ROOT"

echo "══════════════════════════════════════════════════"
echo "  GameThread — Local Pipeline Tunnel Startup"
echo "══════════════════════════════════════════════════"

# ── Step 1: Cloud SQL Proxy ───────────────────────────────────────────────────
echo ""
echo "Step 1/4: Checking Cloud SQL Proxy..."
if lsof -i ":$PROXY_PORT" -sTCP:LISTEN -t &>/dev/null; then
  echo "  ✅ Cloud SQL Proxy already running on port $PROXY_PORT"
else
  echo "  Starting Cloud SQL Proxy on port $PROXY_PORT..."
  "$PROXY_BINARY" "$CLOUD_SQL_INSTANCE" --port "$PROXY_PORT" &
  PROXY_PID=$!
  echo "  ✅ Proxy started (PID=$PROXY_PID)"
  sleep 3
fi

# ── Step 2: Local FastAPI backend ─────────────────────────────────────────────
echo ""
echo "Step 2/4: Checking local FastAPI backend..."
if curl -s "http://localhost:$API_PORT/healthz" &>/dev/null; then
  echo "  ✅ Backend already running on port $API_PORT"
else
  echo "  Starting FastAPI backend on port $API_PORT..."
  cd "$BACKEND_DIR"
  source venv/bin/activate
  EMBEDDED_SCHEDULER_ENABLED=false \
  uvicorn main:app --host 0.0.0.0 --port "$API_PORT" --workers 1 \
    >> "$REPO_ROOT/logs/local-api.log" 2>&1 &
  API_PID=$!
  echo "  ✅ Backend started (PID=$API_PID)"
  sleep 4
  cd "$REPO_ROOT"
fi

# ── Step 3: ngrok tunnel ──────────────────────────────────────────────────────
echo ""
echo "Step 3/4: Starting ngrok tunnel..."
pkill -f "ngrok http $API_PORT" 2>/dev/null || true
sleep 2
ngrok http "$API_PORT" --log=stdout > /tmp/ngrok-gamethread.log 2>&1 &
NGROK_PID=$!
echo "  Waiting for tunnel to establish..."
sleep 5

NGROK_URL=$(curl -s "http://localhost:$NGROK_PORT/api/tunnels" 2>/dev/null | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    if t.get('proto') == 'https':
        print(t['public_url'])
        break
" 2>/dev/null || echo "")

if [ -z "$NGROK_URL" ]; then
  echo "  ❌ Failed to get ngrok URL. Check /tmp/ngrok-gamethread.log"
  exit 1
fi

echo "  ✅ Tunnel live: $NGROK_URL"

# ── Step 4: Update Composer Airflow Variable ──────────────────────────────────
echo ""
echo "Step 4/4: Updating Composer Airflow Variable..."
gcloud composer environments run "$COMPOSER_ENV" \
  --location="$COMPOSER_REGION" \
  --project="$COMPOSER_PROJECT" \
  variables set -- GAMETHREAD_API_BASE_URL "$NGROK_URL" 2>&1 | tail -3

echo ""
echo "══════════════════════════════════════════════════"
echo "  ✅ All systems ready!"
echo ""
echo "  Local API:     http://localhost:$API_PORT"
echo "  ngrok tunnel:  $NGROK_URL"
echo "  ngrok UI:      http://localhost:$NGROK_PORT"
echo ""
echo "  Airflow variable GAMETHREAD_API_BASE_URL updated."
echo ""
echo "  To trigger a DAG run:"
echo "    gcloud composer environments run $COMPOSER_ENV \\"
echo "      --location=$COMPOSER_REGION dags trigger -- gamethread_cloud_pipeline"
echo ""
echo "  ⚠️  Keep this terminal open. Closing it kills the tunnel."
echo "  ⚠️  ngrok free URL changes every restart — run this script again to update Composer."
echo "══════════════════════════════════════════════════"

# Keep alive and show tunnel logs
wait $NGROK_PID
