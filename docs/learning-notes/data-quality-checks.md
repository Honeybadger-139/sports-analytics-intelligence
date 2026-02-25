# Data Quality & Pipeline Auditing

🎓 **WHAT ARE DATA QUALITY CHECKS?**
In professional ML systems, your model is only as good as the data feeding it. Data quality checks are automated validations that ensure your dataset is complete, consistent, and free of "silent failures."

## Why Auditing Matters
- **Silent Failures**: The API might return 200 OK but give empty results for one team.
- **Data Gaps**: A player might be missing from a box score, breaking feature calculation.
- **Schema Drift**: Column names might change, leading to NULL values.

## Our Resilience Pattern

### 1. Pre-flight Checks (Connectivity)
Before starting a long-running sync, we verify:
- **Database Connectivity**: Is PostgreSQL reachable?
- **API Connectivity**: Is the NBA Stats API responding to a heartbeat?

### 2. Post-flight Checks (Audit logic)
After the data is loaded, we run SQL queries to verify:
- **Match Consistency**: Does every completed game have exactly 2 team records?
- **Player Stats**: Are there any completed games with zero player box scores?
- **Critical Nulls**: Are there NULL scores for games marked as completed?

### 3. Pipeline Audit Table
We record every sync event in a `pipeline_audit` table. This provides a "flight recorder" for the system.

| Field | Purpose |
| :--- | :--- |
| `module` | Which part of the system ran (ingestion vs feature_store) |
| `status` | success or failed |
| `processed` | Total records handled |
| `inserted` | Records actually saved (upserts counted) |
| `errors` | Traceback or error message for debugging |
| `details` | JSON breakdown of record types and timing |

## Interview Angle
> "I implemented a persistent auditing layer for our data pipeline. Instead of just printing logs to the console, I structured sync results into a database table. This allowed me to build a health dashboard and proactively detect data quality issues before they reached the model training stage."

## Senior Architect Perspective
> "A data pipeline without an audit trail is a liability. By recording record counts and error messages in a structured way, we've moved from reactive debugging to proactive observability. This reduces MTTR (Mean Time To Recovery) when APIs change or data inconsistencies appear."
