# Pub/Sub Push Subscription: Prefect Feature Trigger

This document captures the Cloud Pub/Sub push subscription used to hand off
successful ingestion runs to Prefect.

## Subscription

- Topic: `pipeline-events`
- Subscription name: `prefect-feature-trigger`
- Delivery mode: push
- Target endpoint: `https://gamethread-pubsub-trigger-{hash}.run.app/trigger`

## Message Contract

The ingestion job publishes JSON with this shape:

```json
{
  "run_id": "20260320_063000",
  "status": "success",
  "seasons": ["2025-26"],
  "rows_ingested": {
    "matches": 12,
    "team_game_stats": 24,
    "player_game_stats": 180
  },
  "gcs_prefix": "gs://gamethread-raw/2026/03/20/",
  "ingestion_completed_at": "2026-03-20T01:00:00Z"
}
```

The bridge only triggers Prefect when:

- `status == "success"`
- `rows_ingested.matches > 0`

## Retry Policy

- Ack deadline: `60s`
- Retry policy: exponential backoff
- Maximum retries: `5`

## Auth

- Auth type: OIDC
- Service account: `scheduler-invoker@sports-analytics-intelligence.iam.gserviceaccount.com`

## Operational Notes

- The bridge must always return HTTP `200` so Pub/Sub does not retry forever
  on temporary Prefect or parsing issues.
- Failed ingestion messages are intentionally acknowledged and skipped.
- This keeps ingestion, orchestration, and retry semantics decoupled.
