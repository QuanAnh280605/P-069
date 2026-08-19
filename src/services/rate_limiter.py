"""In-Memory Rate Limiting service and middleware for FastAPI (AI endpoint protection)."""

import asyncio
import logging
import time
from collections import defaultdict
from typing import NamedTuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from src.config import get_settings

logger = logging.getLogger(__name__)

# Endpoints that trigger LLM / AI processing
AI_POST_SUFFIXES = (
    "/semantic/generate",
    "/chat",
    "/metrics/generate",
    "/semantic/import/saved",
    "/semantic/db/connect",
)


class RateLimitResult(NamedTuple):
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int


def get_client_ip(request: Request) -> str:
    """Extract client IP from headers (X-Forwarded-For, X-Real-IP) or direct connection."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class InMemoryRateLimiter:
    """Thread-safe sliding window in-memory rate limiter with periodic cleanup."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._last_cleanup: float = time.time()

    def _cleanup_expired(self, cutoff: float) -> None:
        """Remove keys with no requests remaining in the active window."""
        expired_keys = [k for k, v in self._requests.items() if not v or v[-1] <= cutoff]
        for k in expired_keys:
            del self._requests[k]

    def reset(self) -> None:
        """Reset all rate limiter counters (useful in tests)."""
        self._requests.clear()
        self._last_cleanup = time.time()

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        """Check if request for key is permitted under limit per window_seconds."""
        now = time.time()
        cutoff = now - window_seconds
        async with self._lock:
            if now - self._last_cleanup > 120:
                self._cleanup_expired(cutoff)
                self._last_cleanup = now
            timestamps = [t for t in self._requests[key] if t > cutoff]
            if len(timestamps) >= limit:
                oldest = timestamps[0]
                retry_after = max(1, int(oldest + window_seconds - now) + 1)
                self._requests[key] = timestamps
                return RateLimitResult(allowed=False, limit=limit, remaining=0, retry_after=retry_after)
            timestamps.append(now)
            self._requests[key] = timestamps
            remaining = max(0, limit - len(timestamps))
            return RateLimitResult(allowed=True, limit=limit, remaining=remaining, retry_after=0)


_global_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    """Return the global singleton in-memory rate limiter."""
    return _global_limiter


def is_rate_limiting_active() -> bool:
    """Return True if rate limiting is enabled explicitly or by production environment."""
    settings = get_settings()
    return settings.rate_limit_enabled or settings.app_env == "production"


def is_ai_request(path: str, method: str) -> bool:
    """Return True if the request triggers an AI / LLM invocation."""
    if method.upper() != "POST":
        return False
    normalized = path.rstrip("/")
    return any(normalized.endswith(suffix) for suffix in AI_POST_SUFFIXES)


def build_rate_limit_response(retry_after: int) -> JSONResponse:
    """Build standardized 429 Too Many Requests response with Vietnamese message."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Quá nhiều yêu cầu gọi AI. Vui lòng thử lại sau.",
            "error": "rate_limit_exceeded",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing IP-based rate limiting exclusively on AI requests."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process incoming request and enforce rate limits on AI calls when active."""
        if not is_rate_limiting_active() or not is_ai_request(request.url.path, request.method):
            return await call_next(request)

        settings = get_settings()
        client_ip = get_client_ip(request)
        limiter = get_rate_limiter()
        result = await limiter.check(client_ip, limit=settings.rate_limit_rpm, window_seconds=60)

        if not result.allowed:
            logger.warning(
                "AI rate limit exceeded for IP %s on %s (limit: %d AI requests/min)",
                client_ip,
                request.url.path,
                result.limit,
            )
            return build_rate_limit_response(result.retry_after)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response
