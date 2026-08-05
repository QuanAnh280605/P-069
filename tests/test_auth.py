"""Unit tests for authentication, password hashing, JWT operations, and auth endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    REFRESH_TOKEN_EXPIRE_SECONDS,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)
from src.main import app
from src.models.db import UserModel
from src.services.database import get_db_session


def _dummy_user(user_id: int = 42) -> UserModel:
    """Create a dummy UserModel for testing."""
    return UserModel(
        id=user_id,
        email="test@company.com",
        username="testuser",
        full_name="Test User",
        hashed_password="hashed_dummy",
        role="analyst",
        status="active",
    )


def test_password_hashing() -> None:
    """Test bcrypt password hashing and verification."""
    password = "SecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_access_token_flow() -> None:
    """Test JWT access token creation and payload decoding."""
    user = _dummy_user()
    token = create_access_token(user)
    assert isinstance(token, str)

    payload = decode_jwt_token(token)
    assert payload["sub"] == "42"
    assert payload["email"] == "test@company.com"
    assert payload["role"] == "analyst"
    assert payload["type"] == "access"


def test_jwt_refresh_token_flow() -> None:
    """Test JWT refresh token creation with correct type and longer expiry."""
    user = _dummy_user()
    token = create_refresh_token(user)
    assert isinstance(token, str)

    payload = decode_jwt_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"
    assert "email" not in payload
    assert "role" not in payload


def test_access_and_refresh_tokens_have_different_jti() -> None:
    """Ensure access and refresh tokens have unique JTI values."""
    user = _dummy_user()
    access_payload = decode_jwt_token(create_access_token(user))
    refresh_payload = decode_jwt_token(create_refresh_token(user))
    assert access_payload["jti"] != refresh_payload["jti"]


def test_token_expiry_constants() -> None:
    """Verify token expiry duration constants are sensible."""
    assert ACCESS_TOKEN_EXPIRE_SECONDS == 7 * 24 * 3600
    assert REFRESH_TOKEN_EXPIRE_SECONDS == 30 * 24 * 3600
    assert REFRESH_TOKEN_EXPIRE_SECONDS > ACCESS_TOKEN_EXPIRE_SECONDS


@pytest.mark.asyncio
async def test_register_and_login_api(async_session: AsyncSession) -> None:
    """Test registration and login return both access and refresh tokens."""

    async def _override_db():
        yield async_session

    app.dependency_overrides[get_db_session] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Register user
        reg_payload = {
            "email": "authtest@company.com",
            "username": "authtester",
            "password": "Password123!",
            "full_name": "Auth Tester",
        }
        res_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        data_reg = res_reg.json()
        assert "access_token" in data_reg
        assert "refresh_token" in data_reg
        assert data_reg["token_type"] == "bearer"
        assert data_reg["expires_in"] == ACCESS_TOKEN_EXPIRE_SECONDS
        assert data_reg["user"]["email"] == "authtest@company.com"

        # Login user
        login_payload = {
            "email_or_username": "authtest@company.com",
            "password": "Password123!",
        }
        res_login = await client.post("/api/v1/auth/login", json=login_payload)
        assert res_login.status_code == 200
        data_login = res_login.json()
        assert "access_token" in data_login
        assert "refresh_token" in data_login

        # Get Current User Profile (/me) with access token
        access_token = data_login["access_token"]
        res_me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert res_me.status_code == 200
        assert res_me.json()["email"] == "authtest@company.com"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refresh_endpoint(async_session: AsyncSession) -> None:
    """Test /auth/refresh rotates tokens and revokes old session."""

    async def _override_db():
        yield async_session

    app.dependency_overrides[get_db_session] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Register to get initial tokens
        reg_payload = {
            "email": "refresh@company.com",
            "username": "refreshtester",
            "password": "Password123!",
            "full_name": "Refresh Tester",
        }
        res_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        old_refresh = res_reg.json()["refresh_token"]

        # Refresh tokens
        res_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert res_refresh.status_code == 200
        data = res_refresh.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"] != old_refresh

        # Old refresh token should be revoked now
        res_reuse = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert res_reuse.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(async_session: AsyncSession) -> None:
    """Test /auth/refresh rejects access tokens (only accepts refresh tokens)."""

    async def _override_db():
        yield async_session

    app.dependency_overrides[get_db_session] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        reg_payload = {
            "email": "reject@company.com",
            "username": "rejecttester",
            "password": "Password123!",
            "full_name": "Reject Tester",
        }
        res_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        access_token = res_reg.json()["access_token"]

        res_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert res_refresh.status_code == 401

    app.dependency_overrides.clear()
