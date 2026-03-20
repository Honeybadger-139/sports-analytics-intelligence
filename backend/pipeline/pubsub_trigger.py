"""
Pub/Sub push subscription bridge for Prefect feature engineering.

This service receives ingestion completion messages and turns successful runs
into Prefect flow runs. It always returns HTTP 200 so Pub/Sub does not retry
indefinitely on malformed or transient bridge failures.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("gamethread.pubsub_trigger")
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="GameThread Pub/Sub Prefect Bridge", version="1.0.0")

DEPLOYMENT_NAME = "feature-engineering-pipeline/production"


def _decode_pubsub_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    message = payload.get("message", {})
    data = message.get("data", "")
    if not data:
        return {}

    decoded = base64.b64decode(data).decode("utf-8")
    return json.loads(decoded)


async def _trigger_prefect_flow(run_payload: Dict[str, Any]) -> Optional[str]:
    try:
        from prefect.client.orchestration import get_client
    except Exception as exc:
        logger.warning("Prefect client is unavailable: %s", exc)
        return None

    parameters = {
        "run_id": run_payload.get("run_id", ""),
        "gcs_prefix": run_payload.get("gcs_prefix", ""),
    }

    async with get_client() as client:
        flow_run = await client.create_flow_run_from_deployment(
            deployment_name=DEPLOYMENT_NAME,
            parameters=parameters,
        )
        return str(getattr(flow_run, "id", flow_run))


@app.get("/healthz", include_in_schema=False)
async def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/trigger", include_in_schema=False)
async def trigger(request: Request):
    try:
        payload = await request.json()
        message = _decode_pubsub_message(payload)
        status = message.get("status")
        rows_ingested = message.get("rows_ingested", {}) or {}
        matches = int(rows_ingested.get("matches", 0) or 0)

        if status != "success":
            logger.info("Skipping Prefect trigger because ingestion status=%s", status)
            return JSONResponse(status_code=200, content={"acknowledged": True, "triggered": False})

        if matches <= 0:
            logger.info("Skipping Prefect trigger because matches=%s", matches)
            return JSONResponse(status_code=200, content={"acknowledged": True, "triggered": False})

        flow_run_id = await _trigger_prefect_flow(message)
        logger.info(
            "Triggered Prefect flow run from Pub/Sub message",
            extra={
                "run_id": message.get("run_id"),
                "gcs_prefix": message.get("gcs_prefix"),
                "flow_run_id": flow_run_id,
            },
        )
        return JSONResponse(
            status_code=200,
            content={
                "acknowledged": True,
                "triggered": True,
                "flow_run_id": flow_run_id,
            },
        )
    except Exception as exc:
        logger.exception("Pub/Sub trigger bridge encountered a non-fatal error: %s", exc)
        return JSONResponse(status_code=200, content={"acknowledged": True, "triggered": False, "error": str(exc)})
