# Query Tools — pgAdmin & Database Exploration

## What Is pgAdmin?

pgAdmin is the **official web-based administration tool** for PostgreSQL. Think of it like a SQL Lab — you can write queries, browse table schemas, view results in a grid, and export to CSV. It's the visual counterpart to the `psql` command-line tool.

> **Analogy**: If PostgreSQL is the database engine, pgAdmin is the **dashboard on the car** — you can see what's inside, run diagnostics, and interact with the engine without popping the hood.

## Why We Added It

During development and debugging, you constantly need to:
- Inspect table contents after an ingestion run
- Test feature engineering SQL before putting it in `feature_store.py`
- Validate data quality (NULL counts, duplicate checks)
- Prototype new queries for model features

Doing all of this via `docker exec ... psql` is painful. pgAdmin gives you a **browser-based SQL editor** with autocomplete, tabular results, and query history.

## How It's Set Up

### Architecture

```
┌──────────────────────────────────────────────────┐
│              Docker Compose Network              │
│                                                  │
│  ┌────────────┐   ┌──────────┐   ┌───────────┐ │
│  │ PostgreSQL │◄──│ FastAPI  │   │  pgAdmin  │ │
│  │  :5432     │   │  :8000   │   │   :5050   │ │
│  └────────────┘   └──────────┘   └─────┬─────┘ │
│        ▲                               │       │
│        └───────────────────────────────┘       │
│         pgAdmin connects via Docker DNS        │
└──────────────────────────────────────────────────┘
        │                                │
   localhost:5432                   localhost:5050
   (psql access)                   (browser access)
```

### Docker Compose Service

```yaml
pgadmin:
  image: dpage/pgadmin4:latest
  container_name: sports-analytics-pgadmin
  restart: unless-stopped
  environment:
    PGADMIN_DEFAULT_EMAIL: admin@sportsanalytics.com
    PGADMIN_DEFAULT_PASSWORD: admin2026
    PGADMIN_LISTEN_PORT: 5050
    PGADMIN_SERVER_JSON_FILE: /pgadmin4/servers.json
  ports:
    - "5050:5050"
  volumes:
    - pgadmin_data:/var/lib/pgadmin           # Persistent settings
    - ./pgadmin-servers.json:/pgadmin4/servers.json:ro  # Auto-registers DB
  depends_on:
    postgres:
      condition: service_healthy
```

### Auto-Server Registration

We mount a `pgadmin-servers.json` file that **pre-configures** the database connection. Without this, you'd have to manually add the server every time the container is recreated.

```json
{
  "Servers": {
    "1": {
      "Name": "Sports Analytics DB",
      "Host": "postgres",
      "Port": 5432,
      "MaintenanceDB": "sports_analytics",
      "Username": "analyst"
    }
  }
}
```

Note: `Host` is `postgres` (the Docker service name), **not** `localhost`. Docker's internal DNS resolves service names to container IPs.

## How to Access

| Field | Value |
|-------|-------|
| **URL** | [http://localhost:5050](http://localhost:5050) |
| **Email** | `admin@sportsanalytics.com` |
| **Password** | `admin2026` |
| **DB Password** (on first connect) | `analytics2026` |

### First-Time Setup

1. Open [http://localhost:5050](http://localhost:5050)
2. Log in with the email/password above
3. In the left sidebar, expand **Sports Analytics DB** → enter DB password `analytics2026`
4. Navigate: **Databases → sports_analytics → Schemas → public → Tables**
5. Right-click any table → **Query Tool** to open SQL Lab

## Key Features

### Query Tool (SQL Lab)

The Query Tool is where you'll spend most of your time:

| Feature | What |
|---------|------|
| **SQL Editor** | Write queries with syntax highlighting and autocomplete |
| **Results Grid** | See output in a tabular format, sortable and filterable |
| **Explain/Analyze** | Visualize query execution plans (see which indexes are hit) |
| **History** | All previous queries saved — searchable |
| **Export** | Download results as CSV, JSON, or copy to clipboard |

### Useful Queries to Try

```sql
-- 1. See all tables and their row counts
SELECT schemaname, relname as table_name, n_live_tup as row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

-- 2. Check if ingestion ran successfully
SELECT COUNT(*) as total_games, 
       MIN(game_date) as earliest, 
       MAX(game_date) as latest
FROM matches;

-- 3. Preview computed features
SELECT * FROM match_features 
ORDER BY game_date DESC 
LIMIT 20;

-- 4. Check for NULL features (data quality)
SELECT 
    COUNT(*) as total,
    COUNT(home_win_pct_last_5) as has_win_pct,
    COUNT(home_point_diff_5) as has_point_diff
FROM match_features;

-- 5. Test a new feature idea before adding to feature_store.py
SELECT team_id, game_date,
    AVG(points) OVER (
        PARTITION BY team_id 
        ORDER BY game_date 
        ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
    ) as avg_points_last_3
FROM team_game_stats
ORDER BY team_id, game_date DESC
LIMIT 30;
```

## CLI Alternative: `psql` via Docker

For quick one-liners without opening a browser:

```bash
# List all tables
docker exec -it sports-analytics-db psql -U analyst -d sports_analytics -c "\dt"

# Run a query
docker exec -it sports-analytics-db psql -U analyst -d sports_analytics \
  -c "SELECT COUNT(*) FROM teams;"

# Interactive session
docker exec -it sports-analytics-db psql -U analyst -d sports_analytics
```

## Hosting on a Server

Since pgAdmin is a Docker Compose service, deploying to a server is straightforward:

```bash
# On any server with Docker installed:
git clone <your-repo>
docker-compose up -d
# pgAdmin is now accessible at http://<server-ip>:5050
```

**For production access**, add:
- **Reverse proxy** (Nginx/Traefik) in front of port 5050
- **SSL/TLS certificate** (Let's Encrypt) for HTTPS
- **Firewall rules** to restrict access to your IP only
- **Stronger credentials** via environment variables

## Interview Angle

> **"How do you explore and validate your data during development?"**
>
> "I integrated pgAdmin as a Docker Compose service alongside PostgreSQL. It gave me a browser-based SQL editor to prototype feature engineering queries, validate data quality after ingestion runs, and inspect execution plans. Having the query tool as part of the development environment — not a separate install — meant any teammate could explore the data immediately after `docker-compose up`."
