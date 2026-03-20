# Cloud Monitoring and Alerting

## What Cloud Monitoring Does

Cloud Monitoring is Google Cloud's managed observability system for metrics, logs, and alerting. In this platform, we use it to record custom ML health signals and page the team when those signals drift outside safe bounds.

## Why Custom Metrics Matter

Custom metrics turn ML-specific events into first-class operational signals:

- `prediction_confidence`
- `data_freshness_hours`
- `model_accuracy`
- `feature_null_rate`
- `retrain_triggered`

That lets us alert on data and model quality, not just infrastructure uptime.

## How Alerting Works

The usual flow is:

1. Emit a custom metric from the API, feature pipeline, or monitoring job.
2. Define an alerting policy in Cloud Monitoring.
3. Route notifications to email, SMS, or on-call tooling.
4. Investigate whether the issue is data drift, ingestion lag, or model decay.

## Why This Is Better Than Ad Hoc Logging

Logging can show symptoms, but it is hard to page on and even harder to trend. Metrics are structured, queryable, and easy to threshold. That makes them a better fit for production ML operations.

## Practical Examples

- If `feature_null_rate` spikes, the upstream ingestion contract may be broken.
- If `data_freshness_hours` grows past 48, the ingestion job may have stalled.
- If `prediction_confidence` falls across many games, the model may be facing distribution shift.
- If `model_accuracy` decays over several days, it may be time to retrain.

## Interview Questions

1. Why would you use custom metrics instead of only logs for ML monitoring?
2. What is the difference between a data freshness alert and a model quality alert?
3. How do you prevent alert fatigue in a production ML system?
4. Why is a non-blocking metric writer important inside an API request path?
5. How would you choose thresholds for confidence or accuracy alerts?

## Takeaway

Cloud Monitoring gives this platform a shared operational language between data engineering, ML engineering, and SRE. It makes quality regressions visible before users notice them.
