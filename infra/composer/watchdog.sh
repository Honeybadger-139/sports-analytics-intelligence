#!/usr/bin/env bash
# ============================================================================
# watchdog.sh — Auto-heal: Cloud SQL Proxy + Docker backend + ngrok tunnel
# ============================================================================
# Idempotent — safe to run when everything is already running.
# Runs at Mac login (via LaunchAgent) and every 30 min (via cron).
#
# What it does:
#   1. Ensures Cloud SQL Proxy is listening on port 5434
#   2. Ensures Docker backend (sports-analytics-api) is running
#   3. Ensures ngrok tunnel is up on port 8000
#   4. Compares ngrok URL to Composer GAMETHREAD_API_BASE_URL variable
#      and updates it if they differ
# ============================================================================

REPO_ROOT="/Users/abhishekgupta/Documents/self-learning/sports-analytics-intelligence"
LOG_FILE="$REPO_ROOT/logs/watchdog.log"
PROXY_BINARY="$REPO_ROOT/cloud-sql-proxy"
CLOUD_SQL_INSTANCE="sports-analytics-intelligence:us-central1:sports-analytics-pg"
PROXY_PORT=5434
API_PORT=8000
NGROK_PORT=4040
COMPOSER_ENV="gamethread-composer"
COMPOSER_REGION="us-central1"
COMPOSER_PROJECT="sports-analytics-intelligence"
DOCKER_COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"
ENV_FILE="$REPO_ROOT/backend/.env"

# ── Logging ───────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"
exec >> "$LOG_FILE" 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "════════════════════════════════════════"
log "Watchdog starting"
log "════════════════════════════════════════"

# ── PATH: ensure gcloud, ngrok, docker are findable ──────────────────────────
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"
# Homebrew on Apple Silicon
[ -f /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"

# ── Step 1: Cloud SQL Proxy ───────────────────────────────────────────────────
log "Step 1/4: Cloud SQL Proxy..."
if lsof -i ":$PROXY_PORT" -sTCP:LISTEN -t &>/dev/null; then
  log "  ✅ Already running on :$PROXY_PORT"
else
  log "  Starting Cloud SQL Proxy..."
  "$PROXY_BINARY" "$CLOUD_SQL_INSTANCE" --port "$PROXY_PORT" \
    >> "$REPO_ROOT/logs/cloud-sql-proxy.log" 2>&1 &
  sleep 4
  if lsof -i ":$PROXY_PORT" -sTCP:LISTEN -t &>/dev/null; then
    log "  ✅ Started"
  else
    log "  ❌ Failed — check logs/cloud-sql-proxy.log"
  fi
fi

# ── Step 2: Docker Desktop readiness ─────────────────────────────────────────
log "Step 2/4: Docker backend..."
DOCKER_WAIT=0
until docker info &>/dev/null || [ $DOCKER_WAIT -ge 90 ]; do
  log "  Waiting for Docker Desktop... (${DOCKER_WAIT}s)"
  sleep 10
  DOCKER_WAIT=$((DOCKER_WAIT + 10))
done

if ! docker info &>/dev/null; then
  log "  ❌ Docker not ready after 90s — skipping backend + ngrok"
  exit 1
fi

# Source .env for CLOUD_SQL_URL, GEMINI_API_KEY, CHAT_API_KEY
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

# Default Cloud SQL URL if not in .env
CLOUD_SQL_URL="${CLOUD_SQL_URL:-postgresql://analyst:cgJzpN2TjkHgAiGTuSPRQtuo@host.docker.internal:5434/sports_analytics}"

if docker ps --filter "name=sports-analytics-api" --filter "status=running" \
     --format "{{.Names}}" 2>/dev/null | grep -q "sports-analytics-api"; then
  log "  ✅ sports-analytics-api already running"
else
  log "  Starting Docker backend..."
  CLOUD_SQL_URL="$CLOUD_SQL_URL" \
  docker compose -f "$DOCKER_COMPOSE_FILE" up -d backend 2>&1 | tail -3
  sleep 6
  if docker ps --filter "name=sports-analytics-api" --filter "status=running" \
       --format "{{.Names}}" 2>/dev/null | grep -q "sports-analytics-api"; then
    log "  ✅ Started"
  else
    log "  ❌ Failed to start — check: docker logs sports-analytics-api"
  fi
fi

# ── Step 3: ngrok ─────────────────────────────────────────────────────────────
log "Step 3/4: ngrok tunnel..."
if curl -s --max-time 3 "http://localhost:$NGROK_PORT/api/tunnels" &>/dev/null; then
  log "  ✅ ngrok already running"
else
  log "  Starting ngrok on port $API_PORT..."
  nohup ngrok http "$API_PORT" --log=stdout \
    > "$REPO_ROOT/logs/ngrok.log" 2>&1 &
  sleep 6
fi

# Fetch ngrok URL
NGROK_URL=$(curl -s --max-time 5 "http://localhost:$NGROK_PORT/api/tunnels" 2>/dev/null | \
  python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for t in data.get('tunnels', []):
        if t.get('proto') == 'https':
            print(t['public_url'])
            break
except Exception:
    pass
" 2>/dev/null || echo "")

if [ -z "$NGROK_URL" ]; then
  log "  ❌ Could not retrieve ngrok URL — check logs/ngrok.log"
  exit 1
fi
log "  Tunnel: $NGROK_URL"

# ── Step 4: Sync Composer variable ────────────────────────────────────────────
log "Step 4/4: Checking Composer variable..."

# Extract just the URL line from gcloud output
CURRENT_URL=$(gcloud composer environments run "$COMPOSER_ENV" \
  --location="$COMPOSER_REGION" \
  --project="$COMPOSER_PROJECT" \
  variables get -- GAMETHREAD_API_BASE_URL 2>/dev/null \
  | grep -Eo 'https://[^[:space:]]+' | head -1 || echo "")

if [ "$CURRENT_URL" = "$NGROK_URL" ]; then
  log "  ✅ Composer variable up to date"
else
  log "  Updating: ${CURRENT_URL:-<empty>} → $NGROK_URL"
  gcloud composer environments run "$COMPOSER_ENV" \
    --location="$COMPOSER_REGION" \
    --project="$COMPOSER_PROJECT" \
    variables set -- GAMETHREAD_API_BASE_URL "$NGROK_URL" 2>&1 | tail -3
  log "  ✅ Composer variable updated"
fi

log "════════════════════════════════════════"
log "Watchdog complete — all systems ready"
log "════════════════════════════════════════"
