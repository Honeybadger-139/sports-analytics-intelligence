# =============================================================================
# Sports Analytics Intelligence — Project Commands
# =============================================================================
# Usage:
#   make install   — first-time setup (install all dependencies)
#   make build     — compile the React frontend into frontend/dist/
#   make start     — build frontend + start backend on localhost:8000
#   make dev       — start backend (8000) + Vite dev server (5174) for coding
#   make db-start  — start the PostgreSQL Docker container
#   make stop      — stop the backend server
# =============================================================================

.PHONY: install build start dev db-start stop

# ── Paths ────────────────────────────────────────────────────────────────────
BACKEND_DIR   := backend
FRONTEND_DIR  := frontend
PYTHON        := $(BACKEND_DIR)/venv/bin/python
UVICORN       := $(BACKEND_DIR)/venv/bin/uvicorn
DB_CONTAINER  := sports-analytics-db

# ── Install all dependencies (run once after cloning) ─────────────────────
install:
	@echo "→ Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm ci
	@echo "→ Installing backend dependencies..."
	cd $(BACKEND_DIR) && python3 -m venv venv && venv/bin/pip install -q -r requirements.txt
	@echo ""
	@echo "✓ Installation complete."
	@echo "  Next: copy backend/.env.example → backend/.env and fill in your API keys."
	@echo "  Then run: make db-start && make start"

# ── Build the React frontend for production ────────────────────────────────
build:
	@echo "→ Building frontend..."
	cd $(FRONTEND_DIR) && npm run build
	@echo "✓ Frontend built at frontend/dist/"

# ── Start backend only on localhost:8000 (includes build step) ────────────
start: build
	@echo "→ Stopping any existing backend on port 8000..."
	@lsof -ti :8000 | xargs kill -9 2>/dev/null || true
	@sleep 1
	@echo "→ Starting backend on http://localhost:8000 ..."
	cd $(BACKEND_DIR) && $(UVICORN) main:app --host 0.0.0.0 --port 8000 --reload

# ── Dev mode: backend (8000) + Vite hot-reload (5174) ─────────────────────
dev:
	@echo "→ Stopping any existing backend on port 8000..."
	@lsof -ti :8000 | xargs kill -9 2>/dev/null || true
	@echo "→ Stopping any existing Vite server on port 5174..."
	@lsof -ti :5174 | xargs kill -9 2>/dev/null || true
	@sleep 1
	@echo "→ Starting backend on http://localhost:8000 (background)..."
	@cd $(BACKEND_DIR) && $(UVICORN) main:app --host 0.0.0.0 --port 8000 --reload &
	@sleep 2
	@echo "→ Starting Vite dev server on http://localhost:5174 ..."
	@echo "   (API calls are proxied to localhost:8000 automatically)"
	cd $(FRONTEND_DIR) && npm run dev

# ── Start the PostgreSQL Docker container ─────────────────────────────────
db-start:
	@echo "→ Starting PostgreSQL container ($(DB_CONTAINER))..."
	@docker start $(DB_CONTAINER) 2>/dev/null || \
		echo "  ✗ Container '$(DB_CONTAINER)' not found. Make sure Docker Desktop is running."
	@echo "✓ PostgreSQL ready."

# ── Stop the backend server ────────────────────────────────────────────────
stop:
	@echo "→ Stopping backend on port 8000..."
	@lsof -ti :8000 | xargs kill -9 2>/dev/null || true
	@echo "→ Stopping Vite dev server on port 5174..."
	@lsof -ti :5174 | xargs kill -9 2>/dev/null || true
	@echo "✓ All servers stopped."
