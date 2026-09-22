import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.i18n import t_req
from app.models import User


class TokenBucket:
    """In-memory token bucket keyed by an arbitrary string.

    Per-process only: with a single uvicorn worker this is a global limit;
    with N workers the effective limit is N times the configured rate.
    """

    def __init__(self, rate: int, per_seconds: int):
        self.rate = rate
        self.per_seconds = per_seconds
        self._state: dict[str, tuple[float, float]] = {}

    def _refill(self, key: str, now: float) -> tuple[float, float]:
        tokens, last = self._state.get(key, (float(self.rate), now))
        elapsed = now - last
        tokens = min(float(self.rate), tokens + elapsed * self.rate / self.per_seconds)
        return tokens, now

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self._refill(key, now)
        if tokens < 1.0:
            self._state[key] = (tokens, last)
            return False
        self._state[key] = (tokens - 1.0, last)
        return True

    def retry_after(self, key: str) -> int:
        tokens, _ = self._state.get(key, (1.0, 0.0))
        missing = max(0.0, 1.0 - tokens)
        seconds = missing * self.per_seconds / self.rate
        return max(1, int(seconds + 0.999))


_limiter = None


def get_limiter() -> TokenBucket:
    global _limiter
    if _limiter is None:
        from app.config import settings

        _limiter = TokenBucket(settings.rate_limit_extract, 60)
    return _limiter


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_key(request: Request, user: User | None) -> str:
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{_client_ip(request)}"


def apply_rate_limit(request: Request, bucket: TokenBucket, user: User | None = None) -> JSONResponse | None:
    key = rate_limit_key(request, user)
    if bucket.allow(key):
        return None
    return JSONResponse(
        status_code=429,
        content={"detail": t_req("Too many requests, please slow down")},
        headers={"Retry-After": str(bucket.retry_after(key))},
    )
