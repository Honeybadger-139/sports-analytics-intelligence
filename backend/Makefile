# Makefile for Sports Analytics Intelligence Pipeline

.PHONY: help setup ingest features train run-api test lint all

# Default help command
help:
	@echo "🏀 Sports Analytics Intelligence Pipeline Control"
	@echo "================================================"
	@echo "Available commands:"
	@echo "  make setup      - Install dependencies and setup environment"
	@echo "  make ingest     - Run the full data ingestion pipeline"
	@echo "  make features   - Run the feature engineering pipeline"
	@echo "  make train      - Train ML prediction models"
	@echo "  make run-api    - Start the FastAPI backend server"
	@echo "  make test       - Run the test suite"
	@echo "  make lint       - Check code style"
	@echo "  make all        - Run ingestion → features → train → start API"

# Setup environment
setup:
	@echo "📦 Setting up environment..."
	pip install -r requirements-dev.txt

# Run data ingestion
ingest:
	@echo "🚀 Starting Data Ingestion..."
	PYTHONPATH=. python src/data/ingestion.py

# Run feature engineering
features:
	@echo "⚙️  Starting Feature Engineering..."
	PYTHONPATH=. python src/data/feature_store.py

# Train ML models
train:
	@echo "🧠 Training ML Models..."
	PYTHONPATH=. python src/models/trainer.py

# Start the API server
run-api:
	@echo "🌐 Starting API Server..."
	PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port 8000

# Run tests
test:
	@echo "🧪 Running Tests..."
	PYTHONPATH=. pytest tests/ -v --tb=short

# Lint check
lint:
	@echo "🔍 Checking code style..."
	python -m py_compile src/data/ingestion.py
	python -m py_compile src/data/feature_store.py
	python -m py_compile src/models/trainer.py
	python -m py_compile src/models/predictor.py
	python -m py_compile src/models/explainability.py
	python -m py_compile src/models/bet_sizing.py
	python -m py_compile src/api/routes.py
	python -m py_compile main.py
	@echo "✅ All files compile successfully"

# Complete pipeline run
all: ingest features train run-api
