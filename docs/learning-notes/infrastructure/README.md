# 🐳 The Complete Infrastructure Layer — Explained

The Infrastructure Layer is the **operational backbone** of the Sports Analytics Intelligence Platform. It's everything that makes your code actually *run* — containerization, database provisioning, networking, configuration, and environment management.

> **Analogy**: If the Data Layer is the kitchen prep and the ML Engine is the chef, the Infrastructure Layer is the **kitchen itself** — the ovens, refrigerators, plumbing, and electrical wiring. Nobody sees it during the meal, but without it, nothing works.

---

## Architecture Position

```
┌─────────────────────────────────────────────────────────┐
│               INFRASTRUCTURE  ◄── You are here           │
│                                                         │
│  ┌──────────────────┐    ┌────────────────────────┐    │
│  │  Docker Compose   │    │  Environment Config     │    │
│  │  (Orchestrator)   │    │  (.env + settings.yaml) │    │
│  └──────┬───────────┘    └────────────────────────┘    │
│         │                                               │
│    ┌────┴────────────────────┐                          │
│    │         Services        │                          │
│    ├─────────────┬───────────┤                          │
│    │  PostgreSQL │  FastAPI  │                          │
│    │  (port 5432)│ (port 8000)│                          │
│    └─────────────┴───────────┘                          │
│         │                                               │
│    ┌────┴──────────┐                                    │
│    │   Volumes     │                                    │
│    │  postgres_data│ (persistent DB storage)             │
│    │  ./backend    │ (bind mount for live reload)        │
│    └───────────────┘                                    │
└─────────────────────────────────────────────────────────┘
```

---

## Files in This Folder

| File | Topic | Key Concepts |
|------|-------|-------------|
| [docker-containerization.md](docker-containerization.md) | **Docker & Containerization** — How we package and run the entire platform | Dockerfile vs Compose, volumes, health checks, networking, layer caching |

---

## What the Infrastructure Layer Contains

Our infrastructure has **4 key components**:

### 1. Docker Compose (`docker-compose.yml`) — The Orchestrator

Docker Compose coordinates **multiple containers** that need to work together. In our case:

```yaml
services:
  postgres:      # PostgreSQL 16 Alpine — the database
    image: postgres:16-alpine
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data        # Persistent storage
      - ./backend/src/data/init.sql:/docker-entrypoint-initdb.d/init.sql  # Auto-setup
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U analyst"]    # Ready check

  backend:       # FastAPI application — the ML engine
    build: ./backend
    ports: ["8000:8000"]
    depends_on:
      postgres:
        condition: service_healthy                     # Wait for DB
    volumes:
      - ./backend:/app                                 # Live reload
```

**Why Docker Compose over just Docker?**

| | Just Docker | Docker Compose |
|--|----|---|
| **Start** | `docker run postgres` then `docker run backend` manually | `docker-compose up` — one command |
| **Networking** | Manual network creation, IP management | Auto-creates internal network, service names = hostnames |
| **Dependencies** | No dependency ordering | `depends_on` + health checks |
| **Teardown** | Kill each container separately | `docker-compose down` — stops everything |

> **🎯 Interview angle**: *"I containerized the stack with Docker Compose for reproducibility — any team member can run `docker-compose up` and have a PostgreSQL database, initialized schema, and FastAPI server running in under 60 seconds."*

### 2. PostgreSQL Container — The Database Server

Key configuration choices:

| Setting | Value | Why |
|---------|-------|-----|
| **Image** | `postgres:16-alpine` | Alpine = ~50MB vs ~400MB for full image. Smaller attack surface. |
| **Restart policy** | `unless-stopped` | Auto-restart on crash — production resilience |
| **Health check** | `pg_isready` every 10s | Backend won't start until DB is accepting connections |
| **Init script** | `init.sql` mounted to `/docker-entrypoint-initdb.d/` | Schema auto-created on first boot — 7 tables + indexes |
| **Named volume** | `postgres_data` | Data persists across `docker-compose down/up` cycles |

**Critical gotcha**: Without the named volume, stopping PostgreSQL would **delete all your data**. Named volumes survive container restarts and recreations.

**Another critical gotcha**: Init scripts only run on **first start** (empty data volume). Schema changes after initial setup need Alembic migrations.

### 3. FastAPI Container — The Application Server

| Setting | Value | Why |
|---------|-------|-----|
| **Build context** | `./backend` | Dockerfile lives in the backend directory |
| **Port** | `8000:8000` | Maps container port to host for API access |
| **Depends on** | `postgres: service_healthy` | Won't start until PostgreSQL health check passes |
| **Bind mount** | `./backend:/app` | Code changes reflect immediately — no rebuild needed during dev |
| **DATABASE_URL** | `@postgres:5432` | Uses Docker's internal DNS — `postgres` hostname resolves to the DB container |

### 4. Environment Configuration — `.env` + `settings.yaml`

We use a **two-layer config system**:

```
┌─────────────────────────────────┐
│  .env (secrets + infra)         │  ← Never committed to Git
│  POSTGRES_USER=analyst          │
│  POSTGRES_PASSWORD=analytics2026│
│  GEMINI_API_KEY=xxx             │
└─────────────────┬───────────────┘
                  │ injected via Docker
                  ▼
┌─────────────────────────────────┐
│  settings.yaml (app config)     │  ← Committed to Git
│  rolling_windows: 5, 10         │
│  kelly_fraction: 0.25           │
│  cv_folds: 5                    │
└─────────────────────────────────┘
```

**Why two files?**
- `.env` holds **secrets** (passwords, API keys) — never in Git
- `settings.yaml` holds **tunable parameters** (model hyperparameters, risk thresholds) — version-controlled so you can track what changed

> **🎯 Interview angle**: *"I externalized all parameters to YAML. A/B testing a different Kelly fraction or retraining window requires zero code changes — just a config swap."*

---

## Docker Networking (Hidden but Critical)

Docker Compose creates an **internal bridge network** for all services. Within this network:

```
┌──────────────────────────────────────┐
│  Docker Internal Network (bridge)     │
│                                      │
│  postgres  ←→  backend               │
│  (5432)        (8000)                │
│                                      │
│  Service names act as DNS hostnames  │
│  backend connects to "postgres:5432" │
│  (NOT "localhost:5432"!)             │
└──────────────────────────────────────┘
        │
        │ Port mapping
        ▼
┌──────────────────────────────────────┐
│  Host Machine (your laptop)           │
│  localhost:5432 → postgres container │
│  localhost:8000 → backend container  │
└──────────────────────────────────────┘
```

**Key insight**: Inside Docker, containers talk to each other by **service name** (`postgres:5432`), not `localhost`. That's why the `DATABASE_URL` uses `@postgres:5432`, not `@localhost:5432`.

---

## Dockerfile Layer Caching — Build Optimization

```dockerfile
# Step 1: Copy requirements first (changes rarely)
COPY requirements.txt .
RUN pip install -r requirements.txt    # ← Cached if requirements didn't change

# Step 2: Copy application code (changes often)
COPY . .                                # ← Only this re-runs on code changes
```

**Why this order?** Docker caches each layer. If you change `main.py` but not `requirements.txt`:
- Step 1 is cached (pip install **SKIPPED** — saves 2+ minutes)
- Step 2 re-runs (copies new code — takes < 1 second)

If you did `COPY . .` first, ANY code change would invalidate the pip install cache. This is a **build optimization pattern** every Docker user should know.

---

## How Everything Boots Up

When you run `docker-compose up`, here's the exact sequence:

```
1. Docker Compose reads docker-compose.yml
2. Creates internal bridge network
3. Starts PostgreSQL container
   ├── Mounts postgres_data volume (or creates fresh)
   ├── If fresh: runs init.sql → creates 7 tables + indexes
   └── Health check starts: pg_isready every 10s
4. Health check passes → PostgreSQL marked "healthy"
5. Docker starts FastAPI container (depends_on satisfied)
   ├── Builds from Dockerfile (or uses cached image)
   ├── Injects DATABASE_URL via environment
   ├── Bind-mounts ./backend → /app
   └── Runs: uvicorn main:app --host 0.0.0.0 --port 8000
6. Full stack running:
   ├── PostgreSQL at localhost:5432
   └── FastAPI at localhost:8000/docs
```

---

## Production vs. Development Differences

| Concern | Our Dev Setup | Production Would Have |
|---------|--------------|----------------------|
| **Secrets** | `.env` file | AWS Secrets Manager / HashiCorp Vault |
| **Scaling** | Single container | Multiple replicas behind load balancer |
| **Database** | Dockerized PostgreSQL | Managed service (AWS RDS, Cloud SQL) |
| **SSL/TLS** | HTTP only | HTTPS via reverse proxy (Nginx/Traefik) |
| **Logging** | `docker-compose logs` | Centralized logging (ELK, CloudWatch, Datadog) |
| **Resource limits** | None (dev) | `mem_limit`, `cpus` set per container |
| **CI/CD** | Manual `docker-compose up` | Build in CI → push to registry → deploy |

---

## Key Decisions Made

| # | Decision | Why | Interview Angle |
|---|----------|-----|-----------------|
| 1 | **Docker Compose** over bare metal | Reproducible environment, single-command setup | "Any teammate can `docker-compose up` and have the full stack" |
| 2 | **Alpine images** | 50MB vs 400MB — smaller attack surface, faster pulls | "I optimized for image size and security" |
| 3 | **Health checks** | Prevents backend crash from connecting to unready DB | "Service dependency ordering with health checks" |
| 4 | **Named volumes** | Data persistence across container lifecycle | "Database data survives container restarts" |
| 5 | **Two-layer config** | Secrets in `.env`, app config in `settings.yaml` | "Separation of secrets from application configuration" |

---

## Interview Quick Reference

> **"How did you deploy your ML system?"**
>
> "I containerized the entire stack with Docker Compose — PostgreSQL, FastAPI backend, and eventually ChromaDB. Health checks ensure the backend doesn't start until the database is ready. Volumes persist data across restarts. The Dockerfile uses layer caching for fast builds. For production, I'd add a reverse proxy, switch to a managed database like RDS, use a secrets manager, and deploy via CI/CD to ECS or Kubernetes."

> **"What's the difference between Docker and Docker Compose?"**
>
> "Docker manages individual containers. Docker Compose orchestrates multiple containers that need to work together — it handles networking, dependency ordering, volume management, and lifecycle. Think of Docker as managing one truck, and Docker Compose as managing an entire fleet with routing."
