"""Small in-memory sliding-window rate limiter (per process). Fine for one server; when you run
several copies, move the counters to Redis."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, message: str):
        self.limit, self.window, self.message = limit, window_seconds, message
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            retry = int(self.window - (now - q[0])) + 1
            raise HTTPException(429, f"{self.message} Try again in {retry} seconds.", headers={"Retry-After": str(retry)})
        q.append(now)

    def by_ip(self, request: Request) -> None:
        fwd = request.headers.get("x-forwarded-for", "")
        self.check(fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown"))