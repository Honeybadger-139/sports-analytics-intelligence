# Makefile for Sports Analytics Intelligence Pipeline

.PHONY: help setup ingest features run-api all

# Default help command
help:
	@echo "🏀 Sports Analytics Intelligence Pipeline Control"
	@echo "================================================"
	@echo "Available commands:"
	@echo "  make setup      - Install dependencies and setup environment"
	@echo "  make ingest     - Run the full data ingestion pipeline"
	@echo "  make features   - Run the feature engineering pipeline"
	@echo "  make run-api    - Start the FastAPI backend server"
	@echo "  make all        - Run ingestion, then features, then start API"

# Setup environment
setup:
	@echo "📦 Setting up environment..."
	pip install -r requirements.txt

# Run data ingestion
ingest:
	@echo "🚀 Starting Data Ingestion..."
	PYTHONPATH=. python src/data/ingestion.py

# Run feature engineering
features:
	@echo "⚙️  Starting Feature Engineering..."
	PYTHONPATH=. python src/data/feature_store.py

# Start the API server
run-api:
	@echo "🌐 Starting API Server..."
	PYTHONPATH=. python main.py

# Complete pipeline run
all: ingest features run-api
