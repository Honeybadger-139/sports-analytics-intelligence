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
CLOUD_RUN_URL="${CLOUD_RUN_URL:-https://gamethread-api-vxjxsnk3gq-uc.a.run.app}"
DAG_SOURCE="infra/airflow/dags/gamethread_cloud_pipeline.py"

echo "══════════════════════════════════════════════"
echo "  GameThread — Cloud Composer 2 Setup"
echo "══════════════════════════════════════════════"
echo "  Project:       $PROJECT_ID"
echo "  Region:        $REGION"
echo "  Composer Env:  $COMPOSER_ENV"
echo "  Cloud Run URL: $CLOUD_RUN_URL"
echo "  DAG source:    $DAG_SOURCE"
echo "══════════════════════════════════════════════"

# ── Step 1: Enable APIs ──────────────────────────────────────────────────────
echo ""
echo "Step 1/6: Enabling required APIs..."
gcloud services enable \
  composer.googleapis.com \
  secretmanager.googleapis.com \
  --project="$PROJECT_ID" \
  --quiet

# ── Step 2: Create Composer 2 environment (smallest config) ──────────────────
echo ""
echo "Step 2/6: Creating Composer 2 environment (this takes 15-25 minutes)..."
echo "  ⚠️  Composer costs ~\$0.35/hr. Consider using Cloud Scheduler for $0 idle cost."

if gcloud composer environments describe "$COMPOSER_ENV" \
    --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  echo "  ✅ Environment '$COMPOSER_ENV' already exists. Skipping creation."
else
  gcloud composer environments create "$COMPOSER_ENV" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
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

# ── Step 3: Set Airflow Variables (from Secret Manager) ──────────────────────
echo ""
echo "Step 3/6: Setting Airflow variables..."

# Get API key from Secret Manager
CHAT_API_KEY=$(gcloud secrets versions access latest \
  --secret="CHAT_API_KEY" \
  --project="$PROJECT_ID" 2>/dev/null || echo "")

if [ -z "$CHAT_API_KEY" ]; then
  echo "  ⚠️  Secret 'CHAT_API_KEY' not found in Secret Manager."
  echo "  Creating it now..."
  echo -n "$CHAT_API_KEY" | gcloud secrets create CHAT_API_KEY \
    --data-file=- \
    --project="$PROJECT_ID" \
    --replication-policy="automatic" 2>/dev/null || true
  echo "  ⚠️  Please set the secret value manually:"
  echo "     echo -n 'your-key' | gcloud secrets versions add CHAT_API_KEY --data-file=-"
  CHAT_API_KEY="PLACEHOLDER_SET_ME"
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

# ── Step 4: Install Python dependencies ──────────────────────────────────────
echo ""
echo "Step 4/6: Installing Python dependencies in Composer..."

gcloud composer environments update "$COMPOSER_ENV" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --update-pypi-package="requests>=2.31.0"

echo "  ✅ Dependencies installed."

# ── Step 5: Upload DAG ───────────────────────────────────────────────────────
echo ""
echo "Step 5/6: Uploading DAG to Composer..."

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

# ── Step 6: Verify ───────────────────────────────────────────────────────────
echo ""
echo "Step 6/6: Verifying DAG is visible..."
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
