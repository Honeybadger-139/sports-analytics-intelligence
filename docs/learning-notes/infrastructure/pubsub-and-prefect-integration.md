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

## Interview Questions

1. What is the difference between Pub/Sub push and pull delivery?
2. Why would you use a push subscription for pipeline handoffs?
3. What is a Prefect worker pool?
4. Why put a bridge service between Pub/Sub and Prefect?
5. How do you avoid retry storms in event-driven systems?
6. What makes event-driven orchestration easier to evolve than direct coupling?
