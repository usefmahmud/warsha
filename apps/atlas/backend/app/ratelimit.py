"""Tiny in-process sliding-window rate limiter (single worker, v1).

PRD §7.1: 300 req/min per token, 5 failed logins/min per email (AC-01.4).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from .errors import APIError


class SlidingWindow:
    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        return hits

    def retry_after(self, key: str) -> int:
        hits = self._trim(key, time.monotonic())
        if not hits:
            return 0
        return max(1, int(self.window_s - (time.monotonic() - hits[0])) + 1)

    def hit(self, key: str) -> bool:
        """Record a hit. Returns False when the key is over its budget."""
        now = time.monotonic()
        hits = self._trim(key, now)
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def count(self, key: str) -> int:
        return len(self._trim(key, time.monotonic()))

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)

    def clear(self) -> None:
        self._hits.clear()


def too_many(retry_after: int) -> APIError:
    exc = APIError(
        429, "TOO_MANY_ATTEMPTS", "too many attempts, slow down", {"retry_after": retry_after}
    )
    exc.retry_after = retry_after  # type: ignore[attr-defined]
    return exc
