"""
Per-key chatbot guardrails for production abuse prevention.

This module intentionally uses lightweight in-memory counters to enforce:
- requests per minute (per API key)
- daily request quota
- daily estimated token budget
- anomaly throttling for repeated off-topic / expensive prompts

For multi-instance deployments, migrate these counters to Redis.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, status

from src import config


def estimate_tokens(text_value: str) -> int:
    # Conservative approximation for GPT-family tokenization.
    return max(1, int(len(text_value or "") / 4))


def is_expensive_prompt(message: str) -> bool:
    lower = (message or "").lower()
    expensive_markers = (
        "all rows",
        "full table",
        "everything",
        "without limit",
        "all games ever",
        "entire database",
        "dump table",
        "top 1000",
        "top 500",
    )
    return any(marker in lower for marker in expensive_markers)


class ChatAbuseGuard:
    def __init__(self) -> None:
        self._request_window: Dict[str, Deque[float]] = defaultdict(deque)
        self._daily_requests: Dict[Tuple[str, str], int] = defaultdict(int)
        self._daily_tokens: Dict[Tuple[str, str], int] = defaultdict(int)
        self._offtopic_window: Dict[str, Deque[float]] = defaultdict(deque)
        self._expensive_window: Dict[str, Deque[float]] = defaultdict(deque)

    @staticmethod
    def _day_key() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _prune(queue: Deque[float], now_ts: float, window_seconds: int) -> None:
        while queue and (now_ts - queue[0]) > window_seconds:
            queue.popleft()

    def precheck(self, *, api_key: str, message: str, history_chars: int = 0) -> None:
        now_ts = time.time()
        day_key = self._day_key()

        # Per-minute request cap.
        req_queue = self._request_window[api_key]
        self._prune(req_queue, now_ts, 60)
        if len(req_queue) >= config.CHAT_KEY_REQUESTS_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for this API key (requests/minute).",
            )
        req_queue.append(now_ts)

        # Daily request quota.
        request_key = (api_key, day_key)
        if self._daily_requests[request_key] >= config.CHAT_KEY_DAILY_QUOTA:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily chatbot quota exhausted for this API key.",
            )
        self._daily_requests[request_key] += 1

        # Input token budget gate.
        estimated_input_tokens = estimate_tokens(message) + max(1, int(max(history_chars, 0) / 4))
        if estimated_input_tokens > config.CHAT_MAX_ESTIMATED_INPUT_TOKENS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt is too large for this endpoint. Please narrow the request.",
            )

        # Daily token budget.
        token_key = (api_key, day_key)
        if self._daily_tokens[token_key] + estimated_input_tokens > config.CHAT_KEY_DAILY_TOKEN_BUDGET:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily token budget exhausted for this API key.",
            )
        self._daily_tokens[token_key] += estimated_input_tokens

        # Anomaly throttle for expensive prompt patterns.
        if is_expensive_prompt(message):
            expensive_queue = self._expensive_window[api_key]
            self._prune(expensive_queue, now_ts, config.CHAT_ANOMALY_WINDOW_SECONDS)
            expensive_queue.append(now_ts)
            if len(expensive_queue) > config.CHAT_MAX_EXPENSIVE_PER_WINDOW:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many expensive-query prompts in a short window.",
                )

    def record_policy_outcome(self, *, api_key: str, policy_decision: str) -> None:
        if policy_decision != "blocked":
            return
        now_ts = time.time()
        queue = self._offtopic_window[api_key]
        self._prune(queue, now_ts, config.CHAT_ANOMALY_WINDOW_SECONDS)
        queue.append(now_ts)
        if len(queue) > config.CHAT_MAX_OFFTOPIC_PER_WINDOW:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Repeated out-of-scope prompts detected. Please stay within sports analytics scope.",
            )
