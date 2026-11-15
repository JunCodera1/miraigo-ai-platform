"""In-memory sliding-window rate limiter, keyed by caller and bucket.

Per process. Running several replicas needs a shared store (Redis) instead.
"""

from __future__ import annotations

import time
from collections import deque

from japanese_ai.core import errors
from japanese_ai.core.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window:
            hits.popleft()
        if len(hits) >= limit:
            retry = max(1, int(hits[0] + window - now) + 1)
            raise AppError(
                errors.RATE_LIMITED,
                "Too many requests. Slow down and try again.",
                429,
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)
        if len(self._hits) > 50_000:
            self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - window}
