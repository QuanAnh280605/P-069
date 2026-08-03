"""Unit tests for authentication, password hashing, JWT operations, and auth endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.auth import (
    create_access_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)
from src.main import app
from src.models.db import Base, UserModel
from src.services.database import get_db_session

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session():
    """Create in-memory SQLite database session for unit testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def test_password_hashing() -> None:
    """Test bcrypt password hashing and verification."""
    password = "SecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_flow() -> None:
    """Test JWT creation and payload decoding."""
    dummy_user = UserModel(
        id=42,
        email="test@company.com",
        username="testuser",
        full_name="Test User",
        hashed_password="hashed_dummy",
        role="analyst",
        status="active",
    )
    token = create_access_token(dummy_user)
    assert isinstance(token, str)

    payload = decode_jwt_token(token)
    assert payload["sub"] == "42"
    assert payload["email"] == "test@company.com"
    assert payload["role"] == "analyst"


@pytest.mark.asyncio
async def test_register_and_login_api(async_session: AsyncSession) -> None:
    """Test registration and login API endpoints with SQLite test DB."""

    async def _override_db():
        yield async_session

    app.dependency_overrides[get_db_session] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Register user
        reg_payload = {
            "name": "Auth Tester",
            "email": "authtest@company.com",
            "username": "authtester",
            "password": "Password123!",
            "full_name": "Auth Tester",
        }
        res_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        data_reg = res_reg.json()
        assert "access_token" in data_reg
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

        # Get Current User Profile (/me)
        token = data_login["access_token"]
        res_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res_me.status_code == 200
        assert res_me.json()["email"] == "authtest@company.com"

    app.dependency_overrides.clear()
