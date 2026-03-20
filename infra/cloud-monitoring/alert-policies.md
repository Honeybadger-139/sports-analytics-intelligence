# Cloud Monitoring Alert Policies

This document describes the alerting policies to create in Google Cloud Monitoring for the Sports Analytics Intelligence Platform.

## 1. Data Freshness

- Condition: `custom.googleapis.com/pipeline/data_freshness_hours > 48`
- For: 30 minutes
- Notification: email
- Message: `Pipeline may have failed`

## 2. Prediction Error Rate

- Condition: API prediction error rate `> 5%`
- For: 10 minutes
- Notification: email + SMS
- Message: `API serving errors`

## 3. Model Accuracy Regression

- Condition: `custom.googleapis.com/model/accuracy_rolling < 0.55`
- For: 3 consecutive days
- Notification: email
- Message: `Consider manual retrain`

## 4. API Latency

- Condition: API p95 latency `> 5 seconds`
- For: 5 minutes
- Notification: email
- Message: `API performance degraded`

## 5. Prediction Confidence Drift

- Condition: `custom.googleapis.com/model/prediction_confidence` mean `< 0.55`
- For: 1 hour
- Notification: email
- Message: `Possible distribution shift`

## Recommended setup notes

- Use the same alerting policy group for production-only signals.
- Prefer notification channels tied to the on-call rotation.
- Keep thresholds versioned alongside the code so changes are auditable.
