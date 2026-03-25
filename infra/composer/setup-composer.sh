#!/usr/bin/env bash
# ============================================================================
# Cloud Composer 2 Setup — GameThread Pipeline
# ============================================================================
# Usage:
#   chmod +x infra/composer/setup-composer.sh
#   ./infra/composer/setup-composer.sh
#
# Prerequisites:
#   - gcloud CLI authenticated with owner/editor role
#   - APIs enabled: composer.googleapis.com, secretmanager.googleapis.com
#   - Secrets already in Secret Manager: CHAT_API_KEY
# ============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT:-sports-analytics-intelligence}"
REGION="${GCP_REGION:-us-central1}"
COMPOSER_ENV="${COMPOSER_ENV_NAME:-gamethread-composer}"
COMPOSER_SA="${COMPOSER_SERVICE_ACCOUNT:-gamethread-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
CLOUD_RUN_SERVICE="${CLOUD_RUN_SERVICE:-gamethread-api}"
CLOUD_RUN_URL="${CLOUD_RUN_URL:-}"
COMPOSER_UPDATE_PYPI_REQUESTS="${COMPOSER_UPDATE_PYPI_REQUESTS:-false}"
DAG_SOURCE="infra/airflow/dags/gamethread_cloud_pipeline.py"

echo "══════════════════════════════════════════════"
echo "  GameThread — Cloud Composer 2 Setup"
echo "══════════════════════════════════════════════"
echo "  Project:       $PROJECT_ID"
echo "  Region:        $REGION"
echo "  Composer Env:  $COMPOSER_ENV"
echo "  Composer SA:   $COMPOSER_SA"
echo "  Cloud Run Svc: $CLOUD_RUN_SERVICE"
echo "  Cloud Run URL: ${CLOUD_RUN_URL:-<auto-resolve>}"
echo "  Update PyPI:   $COMPOSER_UPDATE_PYPI_REQUESTS"
echo "  DAG source:    $DAG_SOURCE"
echo "══════════════════════════════════════════════"

# ── Step 1: Enable APIs ──────────────────────────────────────────────────────
echo ""
echo "Step 1/7: Enabling required APIs..."
gcloud services enable \
  composer.googleapis.com \
  secretmanager.googleapis.com \
  run.googleapis.com \
  --project="$PROJECT_ID" \
  --quiet

if [ -z "$CLOUD_RUN_URL" ]; then
  CLOUD_RUN_URL=$(gcloud run services describe "$CLOUD_RUN_SERVICE" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null || true)
fi

if [ -z "$CLOUD_RUN_URL" ]; then
  echo "❌ Could not resolve Cloud Run URL."
  echo "   Set CLOUD_RUN_URL explicitly or ensure service '$CLOUD_RUN_SERVICE' exists in $REGION."
  exit 1
fi

echo "  ✅ Cloud Run URL: $CLOUD_RUN_URL"

# ── Step 2: Ensure Composer runtime IAM role ──────────────────────────────────
echo ""
echo "Step 2/7: Ensuring Composer runtime IAM bindings..."

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$COMPOSER_SA" \
  --role="roles/composer.worker" \
  --quiet >/dev/null

echo "  ✅ Ensured role roles/composer.worker for $COMPOSER_SA"

# ── Step 3: Create Composer 2 environment (smallest config) ──────────────────
echo ""
echo "Step 3/7: Creating Composer 2 environment (this takes 15-25 minutes)..."
echo "  ⚠️  Composer costs ~\$0.35/hr. Consider using Cloud Scheduler for \$0 idle cost."

ENV_STATE=$(gcloud composer environments describe "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --format="value(state)" 2>/dev/null || true)

if [ "$ENV_STATE" = "ERROR" ]; then
  echo "  ⚠️  Environment '$COMPOSER_ENV' is in ERROR. Deleting for clean recreation..."
  gcloud composer environments delete "$COMPOSER_ENV" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --quiet \
    --async

  echo "  ⏳ Waiting for environment deletion..."
  for _ in $(seq 1 120); do
    if ! gcloud composer environments describe "$COMPOSER_ENV" \
      --location="$REGION" \
      --project="$PROJECT_ID" >/dev/null 2>&1; then
      ENV_STATE=""
      break
    fi
    sleep 30
  done

  if [ -n "$ENV_STATE" ]; then
    echo "  ❌ Timed out waiting for '$COMPOSER_ENV' deletion."
    echo "     Check operation status and rerun once delete completes."
    exit 1
  fi
fi

if [ -n "$ENV_STATE" ]; then
  echo "  ✅ Environment '$COMPOSER_ENV' already exists with state: $ENV_STATE. Skipping creation."
else
  gcloud composer environments create "$COMPOSER_ENV" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --service-account="$COMPOSER_SA" \
    --image-version="composer-2.9.7-airflow-2.9.3" \
    --environment-size=small \
    --scheduler-cpu=0.5 \
    --scheduler-memory=2 \
    --scheduler-storage=1 \
    --web-server-cpu=0.5 \
    --web-server-memory=2 \
    --web-server-storage=1 \
    --worker-cpu=0.5 \
    --worker-memory=2 \
    --worker-storage=1 \
    --min-workers=1 \
    --max-workers=2
fi

# ── Step 4: Set Airflow Variables (from Secret Manager) ──────────────────────
echo ""
echo "Step 4/7: Setting Airflow variables..."

# Get API key from Secret Manager
CHAT_API_KEY=$(gcloud secrets versions access latest \
  --secret="CHAT_API_KEY" \
  --project="$PROJECT_ID" 2>/dev/null || true)

if [ -z "$CHAT_API_KEY" ]; then
  if [ -n "${CHAT_API_KEY_VALUE:-}" ]; then
    echo "  ⚠️  Secret 'CHAT_API_KEY' missing. Creating from CHAT_API_KEY_VALUE..."
    gcloud secrets create CHAT_API_KEY \
      --project="$PROJECT_ID" \
      --replication-policy="automatic" >/dev/null 2>&1 || true
    echo -n "$CHAT_API_KEY_VALUE" | gcloud secrets versions add CHAT_API_KEY \
      --data-file=- \
      --project="$PROJECT_ID" >/dev/null
    CHAT_API_KEY="$CHAT_API_KEY_VALUE"
  else
    echo "  ❌ Secret 'CHAT_API_KEY' not found in Secret Manager."
    echo "     Create it first (or set CHAT_API_KEY_VALUE), then rerun:"
    echo "     echo -n 'your-key' | gcloud secrets create CHAT_API_KEY --data-file=- --replication-policy=automatic"
    echo "     # If secret exists:"
    echo "     echo -n 'your-key' | gcloud secrets versions add CHAT_API_KEY --data-file=-"
    exit 1
  fi
fi

gcloud composer environments run "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  variables set -- \
  GAMETHREAD_API_BASE_URL "$CLOUD_RUN_URL"

gcloud composer environments run "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  variables set -- \
  GAMETHREAD_CHAT_API_KEY "$CHAT_API_KEY"

gcloud composer environments run "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  variables set -- \
  GAMETHREAD_ENV "cloud"

gcloud composer environments run "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  variables set -- \
  GAMETHREAD_PIPELINE_INCLUDE_RAG "false"

gcloud composer environments run "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  variables set -- \
  GAMETHREAD_API_TIMEOUT_SECONDS "7200"

echo "  ✅ Airflow variables configured."

# ── Step 5: Install Python dependencies ──────────────────────────────────────
echo ""
echo "Step 5/7: Installing Python dependencies in Composer..."

if [ "$COMPOSER_UPDATE_PYPI_REQUESTS" = "true" ]; then
  gcloud composer environments update "$COMPOSER_ENV" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --update-pypi-package="requests>=2.31.0"
  echo "  ✅ Dependencies installed."
else
  echo "  ⏭️  Skipped PyPI update (set COMPOSER_UPDATE_PYPI_REQUESTS=true to enable)."
fi

# ── Step 6: Upload DAG ───────────────────────────────────────────────────────
echo ""
echo "Step 6/7: Uploading DAG to Composer..."

if [ ! -f "$DAG_SOURCE" ]; then
  echo "  ❌ DAG file not found: $DAG_SOURCE"
  echo "     Run this script from the repo root."
  exit 1
fi

# Get the DAGs GCS bucket
DAG_BUCKET=$(gcloud composer environments describe "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --format="value(config.dagGcsPrefix)")

gsutil cp "$DAG_SOURCE" "$DAG_BUCKET/"
echo "  ✅ DAG uploaded to $DAG_BUCKET/"

# ── Step 7: Verify ───────────────────────────────────────────────────────────
echo ""
echo "Step 7/7: Verifying DAG is visible..."
sleep 30  # Wait for Airflow to parse the DAG

gcloud composer environments run "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  dags list 2>/dev/null | grep -q "gamethread_cloud_pipeline" && \
  echo "  ✅ DAG 'gamethread_cloud_pipeline' is visible in Composer!" || \
  echo "  ⚠️  DAG not yet visible. It may take 1-2 minutes for Airflow to parse it."

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo ""
echo "  Airflow UI:  Get URL with:"
echo "    gcloud composer environments describe $COMPOSER_ENV \\"
echo "      --location=$REGION --format='value(config.airflowUri)'"
echo ""
echo "  Manual trigger:"
echo "    gcloud composer environments run $COMPOSER_ENV \\"
echo "      --location=$REGION dags trigger -- gamethread_cloud_pipeline"
echo ""
echo "  Update DAG after code changes:"
echo "    gsutil cp $DAG_SOURCE $DAG_BUCKET/"
echo "══════════════════════════════════════════════"
