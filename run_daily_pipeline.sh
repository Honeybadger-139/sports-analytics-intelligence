#!/bin/bash
# ==============================================================================
# Daily NBA Pipeline Automated Runner
# ==============================================================================

# Ensure we are in the correct directory
cd /Users/abhishekgupta/Documents/self-learning/sports-analytics-intelligence

# Add a timestamp to the overall cron log
echo "=============================================================================="
echo "Starting NBA Pipeline run at $(date)"
echo "=============================================================================="

# 1. Start the Cloud SQL proxy in the background to tunnel to GCP
echo "Starting Cloud SQL Proxy..."
curl -sLO https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.0/cloud-sql-proxy.darwin.amd64
chmod +x cloud-sql-proxy.darwin.amd64
./cloud-sql-proxy.darwin.amd64 sports-analytics-intelligence:us-central1:gamethread-db --port 5434 &
PROXY_PID=$!

# Give the proxy a few seconds to establish the connection
sleep 5

# 2. Run the Ingestion Script (Pull from NBA API -> Cloud SQL & GCS)
echo "Running Data Ingestion..."
PYTHONPATH=backend backend/venv/bin/python backend/pipeline/run_ingestion.py

# 3. Run the Feature Engineering Script (Compute advanced metrics in Cloud SQL)
echo "Running Feature Engineering..."
PYTHONPATH=backend backend/venv/bin/python backend/src/data/feature_store.py

# 4. Kill the Proxy when done
echo "Shutting down Cloud SQL Proxy..."
kill $PROXY_PID

echo "=============================================================================="
echo "Pipeline run completed successfully at $(date)"
echo "=============================================================================="
