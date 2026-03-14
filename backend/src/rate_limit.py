"""
Rate limiting helpers with a safe no-op fallback when slowapi is unavailable.
"""

from __future__ import annotations

from typing import Callable

try:
    from slowapi import Limiter  # type: ignore
    from slowapi.errors import RateLimitExceeded  # type: ignore
    from slowapi.extension import _rate_limit_exceeded_handler  # type: ignore
    from slowapi.util import get_remote_address  # type: ignore

    limiter = Limiter(key_func=get_remote_address)
    rate_limit_available = True
except Exception:  # pragma: no cover - exercised in local fallback only
    limiter = None
    RateLimitExceeded = None
    _rate_limit_exceeded_handler = None
    rate_limit_available = False


def limit(rate: str) -> Callable:
    if limiter is None:
        def _decorator(func: Callable) -> Callable:
            return func
        return _decorator
    return limiter.limit(rate)
