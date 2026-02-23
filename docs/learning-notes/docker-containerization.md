# Docker & Containerization — Learning Note

## What Is It?

Docker packages your application and all its dependencies into a **container** — a lightweight, isolated environment that runs the same way on any machine. Think of it like shipping containers: before containers, every port needed custom loading equipment; after containers, any crane can handle any box.

Without Docker: *"But it works on MY machine!"*  
With Docker: *"It works in the container. Your machine IS the container."*

## Why Does It Matter?

In ML/Data Engineering, you often have complex dependency chains:

```
Python 3.11 + PostgreSQL 16 + specific pip packages + environment variables + OS-level libraries
```

If ANY of these differ between your laptop, a teammate's laptop, and production — bugs appear. Docker eliminates this entire class of problems.

**For interviews**: Containerization shows you understand production deployment, not just Jupyter notebooks.

## How Does It Work? (Intuition)

### Our Docker Compose Architecture

```
docker-compose up
       │
       ├──▶ postgres (PostgreSQL 16 Alpine)
       │      ├── Port: 5432
       │      ├── Volume: postgres_data (persistent)
       │      ├── Init: init.sql (auto-creates tables)
       │      └── Healthcheck: pg_isready every 10s
       │
       └──▶ backend (FastAPI app)
              ├── Port: 8000
              ├── Depends on: postgres (healthy)
              ├── Volume: ./backend → /app (live reload)
              └── Env: DATABASE_URL, GEMINI_API_KEY
```

### Key Concepts Explained

#### 1. Dockerfile vs. Docker Compose

| Concept | What It Does | Analogy |
|---------|-------------|---------|
| **Dockerfile** | Builds **one** container image | Recipe for one dish |
| **Docker Compose** | Orchestrates **multiple** containers | Full dinner menu with cooking order |

**Dockerfile** (backend/Dockerfile):
```dockerfile
FROM python:3.11-slim  # Base image
WORKDIR /app           # Set working directory
COPY requirements.txt . # Copy deps first (cache layer)
RUN pip install ...     # Install deps
COPY . .               # Copy app code
CMD ["uvicorn", ...]    # Start command
```

**Docker Compose** (docker-compose.yml) coordinates postgres + backend together.

#### 2. Volumes: Data Persistence

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data  # Named volume
  - ./backend:/app                          # Bind mount
```

| Volume Type | What | When |
|-------------|------|------|
| **Named volume** (`postgres_data`) | Docker manages storage location | Database data — must survive container restart |
| **Bind mount** (`./backend:/app`) | Maps host folder → container folder | Development — live code reload |

**Critical insight**: Without a named volume, stopping PostgreSQL would **delete all your data**. Named volumes persist across `docker-compose down / up` cycles.

#### 3. Health Checks: Service Dependencies

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U analyst"]
  interval: 10s
  timeout: 5s
  retries: 5
```

**Problem**: The backend container starts faster than PostgreSQL. Without a healthcheck, FastAPI tries to connect to a database that isn't ready yet → crash.

**Solution**: `depends_on: { postgres: condition: service_healthy }` tells Docker: *"Don't start the backend until PostgreSQL's healthcheck passes."*

This is a **production pattern**. In Kubernetes, you'd use readiness probes instead.

#### 4. Init Scripts: Auto-Schema Creation

```yaml
volumes:
  - ./backend/src/data/init.sql:/docker-entrypoint-initdb.d/init.sql
```

PostgreSQL's official Docker image automatically runs any `.sql` files in `/docker-entrypoint-initdb.d/` on first start. This means:

1. `docker-compose up -d postgres` → PostgreSQL starts
2. It detects it's a fresh database (no `postgres_data` volume)
3. It runs `init.sql` → creates all 7 tables + indexes
4. Backend connects to a fully-initialized database

**Key gotcha**: Init scripts only run on **first start** (empty data volume). If you need to update the schema later, use Alembic migrations.

#### 5. Environment Variables: Config without Hardcoding

```yaml
environment:
  POSTGRES_DB: ${POSTGRES_DB:-sports_analytics}  # .env file → Docker → container
  DATABASE_URL: postgresql://...@postgres:5432/...
```

The `${VAR:-default}` syntax means: "Use the env var if set, otherwise use the default."

**Why not hardcode?** Because the same docker-compose.yml works for:
- Local development (`localhost:5432`)
- Docker network (`postgres:5432` — service name = hostname!)
- Production (real database URL)

### Docker Networking (Hidden but Critical)

Docker Compose creates an **internal network** for all services. Within this network:
- `postgres` hostname resolves to the PostgreSQL container's IP
- The backend can connect to `postgres:5432` (not `localhost:5432`)

This is why the DATABASE_URL in the backend service uses `@postgres:5432` — it's talking across Docker's internal network.

## Dockerfile Layer Caching

```dockerfile
# Step 1: Copy requirements first
COPY requirements.txt .
RUN pip install -r requirements.txt

# Step 2: Copy application code
COPY . .
```

**Why this order?** Docker caches each layer. If you change `main.py` but not `requirements.txt`:
- Step 1 is cached (pip install SKIPPED — saves 2+ minutes)
- Step 2 re-runs (copies new code — takes < 1 second)

If you did `COPY . .` first, ANY code change would invalidate the pip install cache.

## When to Use vs. Alternatives

| Approach | When to Use | When NOT To |
|----------|-------------|-------------|
| **Docker Compose** (our approach) | Multi-service local dev, CI/CD | Single-process scripts |
| **Kubernetes** | Production at scale (50+ containers) | Local dev, small projects |
| **Bare metal / Virtualenv** | Quick prototyping, single-user | Team collaboration, deployment |
| **Cloud managed (AWS ECS, Cloud Run)** | Production without managing infra | Local development |

## Common Interview Questions

1. **"What's the difference between a Docker image and a container?"**
   → Image is the blueprint (frozen filesystem snapshot). Container is a running instance of that image. You can run 10 containers from 1 image.

2. **"How do you handle secrets in Docker?"**
   → `.env` file (local dev), Docker secrets (Swarm), Kubernetes secrets, or a vault (e.g., AWS Secrets Manager, HashiCorp Vault). **Never bake secrets into the image.**

3. **"Why use Alpine-based images?"**
   → `postgres:16-alpine` is ~50MB vs. `postgres:16` which is ~400MB. Smaller attack surface, faster pulls. Trade-off: some OS packages may be missing.

4. **"What happens when a container crashes?"**
   → `restart: unless-stopped` means Docker automatically restarts it. Without a restart policy, it stays dead until manually restarted.

5. **"How does Docker Compose networking work?"**
   → Compose creates a bridge network. Services reference each other by service name (which acts as a DNS hostname). Each container gets its own IP within the network.

6. **"How would you move this to production?"**
   → Add resource limits, use real secrets management, enable TLS, set up a reverse proxy (Nginx/Traefik), switch to managed databases (RDS), deploy via CI/CD to ECS/Kubernetes.

## The Senior Manager Perspective

A lead architect would think about:
- **Reproducibility**: Any developer can `docker-compose up` and have the full stack running in under 60 seconds. This is non-negotiable for team productivity.
- **Security**: We use `.env` files locally, but in production you'd never pass secrets as environment variables visible in `docker inspect`. Use secret managers.
- **Resource limits**: Without `mem_limit` and `cpus`, a runaway container can starve the host. In production, always set resource constraints.
- **Logging**: `docker-compose logs -f` works for dev. In production, ship logs to a centralized system (ELK, CloudWatch, Datadog).
- **CI/CD**: Docker ensures "works on CI = works in production." Build the image in CI, push to a registry, deploy the same image everywhere.
