# Prefect Flow Design

## What Prefect Adds

Prefect is the orchestration layer for feature engineering. It turns a plain Python pipeline into a graph of tasks with retries, logging, and deployment metadata.

In this project:

- `@task` wraps the individual steps: validate, compute rolling features, compute H2H, compute rest/streak, audit, refresh predictions
- `@flow` wraps the full pipeline execution
- the actual SQL feature logic stays in `backend/src/data/feature_store.py`

## `@flow` vs `@task`

`@flow` defines the overall orchestration boundary.

`@task` defines a unit of work that can retry independently.

Why the split matters:

- a task can retry without rerunning the whole pipeline
- the flow gives us a single deployment and execution history
- the UI shows where the pipeline failed instead of just showing one blob of logs

## Why `exponential_backoff`

`exponential_backoff` spaces out retries so transient infrastructure issues do not get hammered repeatedly.

That is useful for:

- temporary Cloud SQL hiccups
- short-lived API/network errors
- brief Prefect worker warm-up issues

It is better than a fixed retry delay when the failure may need a little more time to clear.

## Task Retry Vs Job Retry

Task-level retry means only the failed step is retried.

Job-level retry means the whole run starts again.

Task-level retry is better here because:

- validation can retry without recomputing all features
- H2H or streak computation can retry independently
- the audit step can stay isolated from the compute steps

## Prefect Deployment

A Prefect deployment is the registered, versioned way to run a flow.

For this project:

- deployment name: `production`
- work pool: `cloud-run-pool`
- flow: `feature-engineering-pipeline`

That gives us a stable orchestration contract that Cloud Scheduler or a Pub/Sub bridge can trigger.

## Prefect Vs Airflow

Prefect is lighter and more Python-native for a small ML platform.

Airflow is stronger when you have a large enterprise DAG estate with many teams and heavyweight scheduling needs.

For this project, Prefect is a better fit because:

- the flow is already Python code
- task retries are the main orchestration need
- the project benefits from a lower-ops setup

## Interview Questions

1. What is the difference between a Prefect flow and a task?
2. Why would you use exponential backoff on task retries?
3. When would you retry a task instead of the whole pipeline?
4. What is a Prefect deployment?
5. Why choose Prefect over Airflow for a smaller ML platform?
6. How does Prefect help with observability?
