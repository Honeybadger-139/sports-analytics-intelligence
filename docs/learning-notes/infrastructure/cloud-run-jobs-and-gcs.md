# Cloud Run Jobs and GCS Raw Storage

## What Is A Cloud Run Job?

A Cloud Run Job is for work that runs to completion and then exits.

Use a job when you want:

- batch ingestion
- one-off backfills
- scheduled maintenance tasks
- export or snapshot workflows

Use a Cloud Run Service when you want:

- always-on HTTP traffic
- request/response APIs
- readiness and liveness checks
- low-latency serving

In this project:

- the FastAPI API stays a Cloud Run Service
- raw ingestion becomes a Cloud Run Job
- RAG refresh becomes a separate Cloud Run Job

## Why Parquet Instead Of CSV?

Parquet is a columnar storage format. CSV is row-oriented text.

Parquet is better for analytics because:

- it compresses well
- it preserves column types
- it is faster for selective reads
- it works well with Spark, DuckDB, BigQuery, and pandas

CSV is simpler, but it is bigger and slower for analytical workloads.
For a data lake, Parquet is the stronger default.

## Why GCS As The Raw Data Lake?

Google Cloud Storage is a good raw landing zone because:

- it is cheap and durable
- it works naturally with Cloud Run jobs
- it keeps the raw data separate from serving databases
- it gives us an audit-friendly snapshot trail

The ingestion job can still upsert into Cloud SQL for API serving, but GCS is the historical snapshot store.

## Why Pub/Sub As A Pipeline Handoff?

Pub/Sub is a decoupled event bus.

In this architecture:

- ingestion finishes
- the job publishes a completion message
- a downstream subscriber triggers feature engineering or refresh logic

That keeps the ingestion job from directly owning the next step.

## When Would You Use Kafka Instead?

Kafka is useful when you need:

- very high throughput
- long event retention
- ordered stream processing at scale
- multiple consumers with replay guarantees

For this project, Pub/Sub is lighter and simpler because we mainly need a reliable handoff signal, not a full streaming platform.

## Interview Questions

1. What is the difference between a Cloud Run Job and a Cloud Run Service?
2. Why is Parquet preferred over CSV for analytics pipelines?
3. Why store raw snapshots in GCS if Cloud SQL already has the data?
4. What problem does Pub/Sub solve in a multi-step pipeline?
5. When would Kafka be a better choice than Pub/Sub?
6. How does decoupling jobs improve reliability?
