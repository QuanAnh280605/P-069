"""Tests for In-Memory Rate Limiter service and middleware (AI endpoints)."""

from starlette.requests import Request
from starlette.testclient import TestClient

from src.config import Settings
from src.main import app
from src.services.rate_limiter import (
    InMemoryRateLimiter,
    get_client_ip,
    get_rate_limiter,
    is_ai_request,
)


def test_get_client_ip_forwarded_for() -> None:
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
    }
    request = Request(scope)
    assert get_client_ip(request) == "203.0.113.195"


def test_get_client_ip_real_ip() -> None:
    scope = {
        "type": "http",
        "headers": [(b"x-real-ip", b"198.51.100.1")],
    }
    request = Request(scope)
    assert get_client_ip(request) == "198.51.100.1"


def test_get_client_ip_direct_connection() -> None:
    scope = {
        "type": "http",
        "headers": [],
        "client": ("192.168.1.50", 54321),
    }
    request = Request(scope)
    assert get_client_ip(request) == "192.168.1.50"


def test_get_client_ip_fallback() -> None:
    scope = {
        "type": "http",
        "headers": [],
    }
    request = Request(scope)
    assert get_client_ip(request) == "127.0.0.1"


def test_is_ai_request() -> None:
    assert is_ai_request("/api/v1/semantic/generate", "POST") is True
    assert is_ai_request("/api/v1/semantic/1/chat", "POST") is True
    assert is_ai_request("/api/v1/semantic/1/metrics/generate", "POST") is True
    assert is_ai_request("/api/v1/semantic/import/saved", "POST") is True
    assert is_ai_request("/api/v1/semantic/db/connect", "POST") is True

    # Non-AI endpoints
    assert is_ai_request("/api/v1/semantic/1/catalog", "GET") is False
    assert is_ai_request("/api/v1/semantic/1/query", "POST") is False
    assert is_ai_request("/api/v1/semantic/1/query/compile", "POST") is False
    assert is_ai_request("/api/v1/auth/login", "POST") is False
    assert is_ai_request("/health", "GET") is False
    assert is_ai_request("/api/v1/semantic/generate", "OPTIONS") is False


async def test_in_memory_limiter_sliding_window() -> None:
    limiter = InMemoryRateLimiter()
    key = "10.0.0.1"

    # First 15 requests should be allowed
    for i in range(15):
        result = await limiter.check(key, limit=15, window_seconds=60)
        assert result.allowed is True
        assert result.remaining == 14 - i

    # 16th request must be rejected
    rejected = await limiter.check(key, limit=15, window_seconds=60)
    assert rejected.allowed is False
    assert rejected.remaining == 0
    assert rejected.retry_after > 0


async def test_in_memory_limiter_reset_and_cleanup() -> None:
    limiter = InMemoryRateLimiter()
    key = "10.0.0.2"
    await limiter.check(key, limit=1, window_seconds=60)
    assert key in limiter._requests

    limiter.reset()
    assert len(limiter._requests) == 0


def test_middleware_disabled_in_development(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.rate_limiter.get_settings",
        lambda: Settings(
            app_env="development",
            rate_limit_enabled=False,
            rate_limit_rpm=2,
            encryption_key="",
        ),
    )
    get_rate_limiter().reset()
    client = TestClient(app)

    # AI request should pass through without rate limit in dev
    for _ in range(5):
        resp = client.post("/api/v1/semantic/generate", json={"db_id": 9999})
        assert resp.status_code != 429


def test_middleware_enforces_rate_limit_on_ai_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.rate_limiter.get_settings",
        lambda: Settings(
            app_env="production",
            rate_limit_enabled=True,
            rate_limit_rpm=3,
            encryption_key="",
        ),
    )
    get_rate_limiter().reset()
    client = TestClient(app)
    headers = {"X-Forwarded-For": "1.2.3.4"}

    # 3 AI calls
    for _ in range(3):
        resp = client.post("/api/v1/semantic/generate", json={"db_id": 9999}, headers=headers)
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" in resp.headers

    # 4th AI call must be rate limited (429)
    resp_blocked = client.post("/api/v1/semantic/generate", json={"db_id": 9999}, headers=headers)
    assert resp_blocked.status_code == 429
    data = resp_blocked.json()
    assert data["error"] == "rate_limit_exceeded"
    assert "Quá nhiều yêu cầu gọi AI" in data["detail"]
    assert "Retry-After" in resp_blocked.headers

    # Non-AI endpoints are NOT blocked even when AI limit is exceeded
    resp_health = client.get("/health", headers=headers)
    assert resp_health.status_code == 200

    resp_catalog = client.get("/api/v1/semantic/nonexistent/catalog", headers=headers)
    assert resp_catalog.status_code != 429


def test_middleware_cors_headers_on_429(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.rate_limiter.get_settings",
        lambda: Settings(
            app_env="production",
            rate_limit_enabled=True,
            rate_limit_rpm=1,
            encryption_key="",
            cors_origins="http://localhost:3000",
        ),
    )
    get_rate_limiter().reset()
    client = TestClient(app)
    headers = {"X-Forwarded-For": "5.6.7.8", "Origin": "http://localhost:3000"}

    # First request consumes quota
    client.post("/api/v1/semantic/generate", json={"db_id": 1}, headers=headers)

    # Second request hits 429 rate limit and MUST retain CORS headers
    resp = client.post("/api/v1/semantic/generate", json={"db_id": 1}, headers=headers)
    assert resp.status_code == 429
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
