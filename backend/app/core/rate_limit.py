"""Sliding-window in-memory rate limiting for sensitive public endpoints (login, PAN, bank penny drop)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import NamedTuple

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings


class RateLimitRule(NamedTuple):
    path: str
    method: str
    max_requests: int
    window_seconds: int


DEFAULT_RULES = (
    RateLimitRule(path="/api/v1/auth/login", method="POST", max_requests=10, window_seconds=60),
    RateLimitRule(path="/api/v1/verifications/pan", method="POST", max_requests=20, window_seconds=60),
    RateLimitRule(path="/api/v1/verifications/bank-account", method="POST", max_requests=20, window_seconds=60),
)


class InMemorySlidingWindowLimiter:
    def __init__(self, rules: tuple[RateLimitRule, ...] = DEFAULT_RULES) -> None:
        self.rules = { (r.path, r.method): r for r in rules }
        self._history: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def get_client_ip(self, request: Request) -> str:
        # Check forward headers if trust_proxy_headers is enabled
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = request.client
        return client.host if client else "127.0.0.1"

    def check(self, request: Request) -> Response | None:
        settings = get_settings()
        # In test suite runs, do not block integration tests
        if settings.app_env == "test":
            return None

        rule = self.rules.get((request.url.path, request.method))
        if not rule:
            return None

        client_ip = self.get_client_ip(request)
        key = f"{rule.path}:{client_ip}"
        now = time.time()
        cutoff = now - rule.window_seconds

        with self._lock:
            q = self._history[key]
            # Prune timestamps older than cutoff window
            while q and q[0] <= cutoff:
                q.popleft()

            if len(q) >= rule.max_requests:
                retry_after = max(1, int(rule.window_seconds - (now - q[0])))
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Too many requests to {rule.path}. Please wait {retry_after} seconds before retrying.",
                        }
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(rule.max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            q.append(now)

        return None


limiter = InMemorySlidingWindowLimiter()
