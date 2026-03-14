"""
Langfuse observability client — Sports Analytics Intelligence Platform
======================================================================

Initialises the Langfuse v3 client once on first access, using keys from
the environment.  When keys are absent the client is not created and all
@observe decorators become transparent pass-throughs (Langfuse v3 default
behaviour — no keys = no OTEL export).

Usage in chat_service.py
------------------------
    from langfuse import observe
    from src.intelligence.langfuse_client import init_langfuse, set_session_context

    @observe(name="chatbot.reply", as_type="chain")
    def reply(self, message, history=None, session_id=None):
        set_session_context(session_id=session_id, user_id="anon")
        ...

Langfuse dashboard will show:
    - One trace per POST /api/v1/chat request
    - Nested spans for intent routing, RAG retrieval, DB query, LLM generation
    - Token usage and model name on each generation span
    - Grouped by session_id (= frontend localStorage session key)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_initialized = False


def _identity_decorator(*args, **kwargs):
    """
    No-op decorator compatible with `@observe(...)` usage.
    """
    if args and callable(args[0]) and len(args) == 1 and not kwargs:
        return args[0]

    def _decorator(func):
        return func

    return _decorator


def _tracing_enabled() -> bool:
    from src import config

    return bool(config.LANGFUSE_ENABLED and config.LANGFUSE_SECRET_KEY)


def _write_fallback_log(
    *,
    model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    latency_ms: Optional[float],
    intent: Optional[str],
    success: bool,
) -> None:
    from src import config

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        "intent": intent or "unknown",
        "success": success,
    }
    try:
        with config.LLM_FALLBACK_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception as exc:
        logger.debug("fallback LLM log write failed: %s", exc)


def observe(*args, **kwargs):
    """
    Safe observe wrapper:
    - returns a no-op decorator when tracing is disabled
    - otherwise delegates to Langfuse's observe decorator
    """
    if not _tracing_enabled():
        return _identity_decorator(*args, **kwargs)
    try:
        from langfuse import observe as _lf_observe

        return _lf_observe(*args, **kwargs)
    except Exception as exc:
        logger.debug("Langfuse observe unavailable, using no-op decorator: %s", exc)
        return _identity_decorator(*args, **kwargs)


def init_langfuse() -> bool:
    """
    Initialise the Langfuse client from environment config.

    Safe to call multiple times — subsequent calls are no-ops.

    Returns True if the client was successfully initialised, False otherwise.
    The @observe decorator works with or without initialisation.
    """
    global _initialized
    if _initialized:
        return True

    from src import config

    if not config.LANGFUSE_ENABLED:
        os.environ.setdefault("OTEL_SDK_DISABLED", "true")
        logger.info("Langfuse: disabled via LANGFUSE_ENABLED=false.")
        return False

    if not config.LANGFUSE_SECRET_KEY:
        os.environ.setdefault("OTEL_SDK_DISABLED", "true")
        logger.warning(
            "Langfuse: LANGFUSE_SECRET_KEY not set in backend/.env — "
            "session tracing and LLM chain observability are disabled. "
            "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable."
        )
        return False

    try:
        from langfuse import Langfuse

        Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
            debug=config.LANGFUSE_DEBUG,
        )
        _initialized = True
        logger.info(
            "Langfuse: client initialised (host=%s, debug=%s)",
            config.LANGFUSE_HOST,
            config.LANGFUSE_DEBUG,
        )
        return True
    except Exception as exc:
        os.environ.setdefault("OTEL_SDK_DISABLED", "true")
        logger.warning("Langfuse: client init failed — %s. Tracing disabled.", exc)
        return False


def set_session_context(
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    trace_name: Optional[str] = None,
) -> None:
    """
    Attach session/user metadata to the currently active Langfuse trace.

    Must be called from inside a function decorated with @observe, after
    the trace has been opened by the decorator.  Safe to call even when
    Langfuse is not initialised — the OTEL span will simply not exist.
    """
    if not _initialized:
        return
    try:
        from opentelemetry import trace as otel_trace
        from langfuse import LangfuseOtelSpanAttributes

        span = otel_trace.get_current_span()
        if span.is_recording():
            if session_id:
                span.set_attribute(LangfuseOtelSpanAttributes.TRACE_SESSION_ID, session_id)
            if user_id:
                span.set_attribute(LangfuseOtelSpanAttributes.TRACE_USER_ID, user_id)
            if trace_name:
                span.set_attribute(LangfuseOtelSpanAttributes.TRACE_NAME, trace_name)
    except Exception as exc:
        logger.debug("set_session_context: could not set OTEL attributes — %s", exc)


def record_generation(
    *,
    name: str,
    prompt: str,
    output: Optional[str],
    model: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    latency_ms: Optional[float] = None,
    intent: Optional[str] = None,
    success: bool = True,
) -> None:
    """
    Record an LLM generation span within the currently active trace.

    Use this inside LLMClient.generate() to capture prompt, response,
    model name, and token counts for every Gemini call.
    """
    if not _initialized:
        _write_fallback_log(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            latency_ms=latency_ms,
            intent=intent or name,
            success=success,
        )
        return
    try:
        from langfuse import get_client

        client = get_client()
        usage = {}
        if input_tokens is not None:
            usage["input"] = input_tokens
        if output_tokens is not None:
            usage["output"] = output_tokens

        with client.start_as_current_generation(
            name=name,
            model=model,
            input=prompt,
            output=output,
            usage_details=usage if usage else None,
        ):
            pass  # span is closed on context manager exit
    except Exception as exc:
        logger.debug("record_generation: could not record Langfuse span — %s", exc)
        _write_fallback_log(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            latency_ms=latency_ms,
            intent=intent or name,
            success=success,
        )
