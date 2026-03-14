"""
Structured logging with per-request trace IDs.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get("-")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "trace_id": getattr(record, "trace_id", "-"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("route", "duration_ms", "status_code", "method"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    _configured = True
