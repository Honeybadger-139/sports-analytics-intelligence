# Learning Note: Cloud Run Deployment Gotchas

> Module: Infrastructure — GCP Cloud Run
> Covers: Cloud SQL socket mounting, Cloud Run Jobs vs Services flag differences, Alembic CI/CD integration, Pydantic ForwardRef in FastAPI

---

## What Is It?

Cloud Run has two distinct primitives:

- **Cloud Run Services** — long-running HTTP servers with autoscaling, ingress, concurrency
- **Cloud Run Jobs** — one-shot batch containers that run to completion

These are different gcloud subcommands (`gcloud run deploy` vs `gcloud run jobs create/update`) and they have **different flag vocabularies**.

---

## Why Does It Matter?

Most Cloud Run tutorials only cover services. When you build a production MLOps platform, you need **jobs** for:
- Alembic schema migrations
- Data ingestion batches
- RAG vector refresh
- Model retraining

Confusing service flags with job flags causes silent failures in CI/CD. Knowing the difference signals that you've operated Cloud Run at the infrastructure level — not just followed a quickstart.

---

## Cloud SQL Flags: The Critical Difference

| Context | Correct Flag | Wrong Flag |
|---------|-------------|------------|
| `gcloud run deploy` (service) | `--add-cloudsql-instances` OR `--set-cloudsql-instances` | — |
| `gcloud run jobs create` | **`--set-cloudsql-instances`** | `--add-cloudsql-instances` ← causes error |
| `gcloud run jobs update` | **`--set-cloudsql-instances`** | `--add-cloudsql-instances` ← causes error |

**Error you'll see if you use the wrong flag on a job:**
```
ERROR: (gcloud.run.jobs.create) unrecognized arguments:
  --add-cloudsql-instances (did you mean '--set-cloudsql-instances'?)
```

**Why `--set` vs `--add`?**
- `--add-cloudsql-instances` appends to the existing connection list (additive, idempotent for services)
- `--set-cloudsql-instances` replaces the entire connection list

For both services and jobs, `--set` is safe when you have a single Cloud SQL instance (which is the common case).

---

## How Cloud SQL Socket Mounting Works

Cloud Run mounts a Unix socket at `/cloudsql/<project>:<region>:<instance>` **only when** the `--set-cloudsql-instances` (or `--add-cloudsql-instances` for services) flag is set at deploy time.

The DATABASE_URL must match: `postgresql+psycopg2://user:password@/dbname?host=/cloudsql/<project>:<region>:<instance>`

**What breaks if you forget the Cloud SQL flag:**
- The socket path doesn't exist in the container → psycopg2 can't connect → `connection refused` errors
- Health checks fail → service routes no traffic → silent failure

**Checking if a revision has Cloud SQL connections:**
Console → Cloud Run → your service → Revisions tab → click revision → "Cloud SQL connections" row

---

## Alembic Migrations in CI/CD: The Right Pattern

**The pattern we use:**
```yaml
# Step N.5 — Run migrations before deploying the service
- name: gcr.io/google.com/cloudsdktool/cloud-sdk
  entrypoint: bash
  args:
    - -c
    - |
      gcloud run jobs update job-run-migrations \
        --image "${IMAGE}:${SHA}" \
        --set-cloudsql-instances "${PROJECT}:${REGION}:${INSTANCE}" \
        --command "alembic" --args "upgrade,head" \
        --quiet 2>/dev/null || \
      gcloud run jobs create job-run-migrations \
        --image "${IMAGE}:${SHA}" \
        --set-cloudsql-instances "${PROJECT}:${REGION}:${INSTANCE}" \
        --update-secrets DATABASE_URL=DATABASE_URL:latest \
        --command "alembic" --args "upgrade,head" \
        --quiet;
      gcloud run jobs execute job-run-migrations --wait --quiet;
```

**Why `update ... || create ...`?**
- First run: `update` fails (job doesn't exist), falls through to `create`
- Subsequent runs: `update` succeeds, skips `create`
- This is idempotent and avoids keeping state about "first time vs subsequent"

**Why `--wait` on execute?**
- Without `--wait`, Cloud Build moves to the next step immediately
- If migrations fail, the API deploy would still proceed — pointing new code at a broken schema
- `--wait` makes Cloud Build block until the migration job completes or fails

**Schema safety guarantee:** If `alembic upgrade head` fails for any reason (bad migration, connection error, conflict), the Cloud Build step exits non-zero → the deploy step never runs → production keeps serving the previous working revision.

---

## The `from __future__ import annotations` Pydantic Trap

### Symptom
```
GET /openapi.json → HTTP 500
PydanticUserError: `ChatRequest` is not fully defined
```

### Root Cause
`from __future__ import annotations` (PEP 563) causes Python to store **all type annotations as strings** at class definition time. When FastAPI tries to generate the OpenAPI schema, Pydantic v2 receives a `ForwardRef('ChatRequest')` string instead of the actual class — and cannot resolve it.

### Fix
Remove `from __future__ import annotations` from any file that defines Pydantic models used in FastAPI route decorators.

```python
# WRONG — breaks Pydantic v2 schema generation
from __future__ import annotations
from pydantic import BaseModel
class ChatRequest(BaseModel):
    message: str

# CORRECT — annotations resolved at class definition time
from pydantic import BaseModel
class ChatRequest(BaseModel):
    message: str
```

### When Is This Import Legitimate?
- Pure Python files with no Pydantic/FastAPI models
- Files where you need forward references to avoid circular imports
- In those cases, add `model_rebuild()` calls after all classes are defined

---

## Common Interview Questions

**Q: How do you run database migrations safely in a Cloud Run deployment?**

Junior answer: "I'd run them in the startup command or in an init container."

Senior answer: "I run them as a pre-deploy Cloud Run Job with `--wait` in the CI/CD pipeline, using the same image as the API service. The build step blocks on the migration job — if Alembic fails, Cloud Build aborts before the service deploy runs. This guarantees the schema is always consistent with the code being deployed. The job reuses existing Cloud SQL IAM and socket-mounting infrastructure, so there's no separate credentials management."

---

**Q: What's the difference between `gcloud run deploy` and `gcloud run jobs`?**

Junior answer: "One is for long-running services and one is for batch tasks."

Senior answer: "They're separate resource types with different lifecycles and flag vocabularies. Services autoscale based on HTTP traffic and have concurrency, min/max instances, and ingress controls. Jobs are for run-to-completion work with task parallelism, timeout, and retry policies. They share the same underlying execution environment (containers, Cloud SQL, secrets, VPC) but `gcloud run jobs create/update` uses `--set-cloudsql-instances` while `gcloud run deploy` uses `--add-cloudsql-instances`. Mixing them up is a common gotcha when you build both in the same pipeline."

---

**Q: Why did your API return 500 on `/openapi.json` but work fine on other endpoints?**

Answer: "I had `from __future__ import annotations` in a route file that defined Pydantic request models. FastAPI generates the OpenAPI schema lazily when the first request hits `/openapi.json` — that's when Pydantic v2 tries to evaluate the ForwardRefs from the PEP 563 string annotations and fails. Regular endpoints worked because they deserialize real request bodies, which use a different code path. The fix was removing that import from the route file."

---

## Senior Manager / Architect Perspective

A senior engineer treats CI/CD pipelines as production infrastructure:

1. **Schema migrations are a gating step** — they block the deploy if they fail. This is non-negotiable for production systems.
2. **Job vs Service flag differences are infrastructure knowledge** — you don't look these up at 2am when prod is down; you know them.
3. **Pydantic/FastAPI annotation behavior is a known gotcha** — if your OpenAPI schema breaks, check `from __future__ import annotations` before anything else.

These are the kinds of details that distinguish engineers who have shipped production MLOps systems from those who have only built demo projects.
