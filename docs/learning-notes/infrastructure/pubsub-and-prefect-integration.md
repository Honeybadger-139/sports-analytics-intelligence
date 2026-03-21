# Pub/Sub And Prefect Integration

## What Is Pub/Sub Push Versus Pull?

Pub/Sub can deliver messages in two common ways:

- Push: Pub/Sub sends the message directly to an HTTP endpoint.
- Pull: a worker polls the subscription and asks for messages.

For this project, push is the better fit because the bridge service can react
immediately when ingestion completes.

## Why Push Is Better Here

Push subscriptions work well for low-latency pipeline handoffs:

- the ingestion job publishes a completion event
- Pub/Sub forwards it to the bridge service
- the bridge decides whether to start Prefect

That keeps the upstream job simple and removes polling logic.

## What Is A Prefect Worker Pool?

A Prefect worker pool is the execution group that receives flow runs from
Prefect Cloud and executes them in a chosen environment.

In this project:

- the pool name is `cloud-run-pool`
- the worker runs as an always-on Cloud Run service
- Prefect Cloud schedules flow runs into that pool

## Why Bridge Pub/Sub To Prefect Instead Of Triggering Prefect Directly?

The bridge isolates delivery semantics from orchestration semantics.

Benefits:

- the ingestion job only publishes an event
- the bridge handles payload validation and flow triggering
- retries on Pub/Sub do not accidentally duplicate orchestration logic

## Prefect Work Pool Types — What They Mean and Who Can Use Them

Prefect offers three categories of work pools:

**Prefect Managed** (`prefect:managed`): Prefect's cloud runs your flows. Zero infrastructure
overhead, but your code must be accessible from Prefect's network and you cannot inject
arbitrary GCP secrets or service accounts. Only viable for simple, dependency-light flows.

**Hybrid** (`prefect-agent`, `process`, `kubernetes`, `cloud-run`): YOUR infrastructure runs a
Prefect worker that pulls work from Prefect Cloud and executes flows locally. This is the
production pattern for enterprise use — your flows run inside your network, have access to
your secrets, and use your compute. **Requires Prefect Cloud Pro or higher.**

**Push** (`cloud-run:push`, `ecs:push`, etc.): Prefect Cloud directly submits work to your
cloud provider, bypassing a persistent worker. More serverless, but still requires a
paid plan.

### What This Means Practically

On the Prefect Cloud free plan:
- Only `prefect:managed` works.
- All hybrid and push pool types return `HTTP 403: "Your plan does not support hybrid or push work pools."`
- This includes `prefect-agent`, `cloud-run:push`, and `process` types.

### The Activation Path (No Code Changes Required)

The architecture for this project is fully implemented. Two options to activate it:

**Option A — Prefect Pro plan**: Upgrade the Prefect Cloud workspace. Set
`PREFECT_API_URL` (already in Secret Manager) on the `prefect-agent` Cloud Run service
and deploy. Zero code changes.

**Option B — Self-hosted Prefect server**: Run `prefect server start` as a Cloud Run
service pointing at the project's existing PostgreSQL instance. Point
`PREFECT_API_URL` to the self-hosted server URL. Self-hosted supports any work pool
type because the plan restriction lives in Prefect Cloud only, not the OSS server.
This is the zero-extra-cost path: our PostgreSQL is already paid for.

### Senior vs Junior Answer

A junior engineer, hitting the 403, would:
- Rewrite the orchestration to not use Prefect
- Or abandon the feature engineering pipeline

A senior engineer:
- Documents the constraint clearly in the decision log
- Preserves the architecture intact — the code is already correct
- Identifies the two-line activation path (plan upgrade or self-hosted URL change)
- Ships smoke tests for everything that IS live and keeps moving

## Interview Questions

1. What is the difference between Pub/Sub push and pull delivery?
2. Why would you use a push subscription for pipeline handoffs?
3. What is a Prefect worker pool?
4. Why put a bridge service between Pub/Sub and Prefect?
5. How do you avoid retry storms in event-driven systems?
6. What makes event-driven orchestration easier to evolve than direct coupling?
7. What is the difference between a Prefect managed work pool and a hybrid work pool?
8. If Prefect Cloud's free plan blocked your deployment, how would you self-host Prefect?
9. A junior rewrites an architecture when hitting a plan limit. What does a senior do differently?
