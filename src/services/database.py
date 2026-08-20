"""Database and Credential Encryption Services.

Provides:
  - Fernet encryption and decryption for target database connection URLs.
  - SQLAlchemy AsyncEngine and AsyncSession management for Metadata Store.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

logger = logging.getLogger(__name__)

_global_engine: AsyncEngine | None = None
_global_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_fernet(key: str | None = None) -> Fernet:
    """Instantiate a Fernet cipher instance using provided key or settings.

    Raises ValueError if no valid encryption key is configured.
    """
    if key:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    settings = get_settings()
    key_str = settings.encryption_key
    if not key_str:
        raise ValueError("encryption_key is not configured. Set ENCRYPTION_KEY in .env file.")
    return Fernet(key_str.encode("utf-8"))


def encrypt_conn_url(plain_url: str, key: str | None = None) -> str:
    """Encrypt plain connection URL using Fernet symmetric key."""
    fernet = _get_fernet(key)
    encrypted_bytes = fernet.encrypt(plain_url.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_conn_url(enc_url: str, key: str | None = None) -> str:
    """Decrypt Fernet-encrypted connection URL string back to plaintext."""
    fernet = _get_fernet(key)
    decrypted_bytes = fernet.decrypt(enc_url.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")


def get_async_engine(db_url: str | None = None) -> AsyncEngine:
    """Create and return a cached SQLAlchemy AsyncEngine instance."""
    global _global_engine, _global_session_factory
    if db_url is None and _global_engine is not None:
        return _global_engine

    url = db_url or get_settings().database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+"):
        parts = url.split("://", 1)
        url = f"postgresql+asyncpg://{parts[1]}"
    elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    engine_kwargs: dict[str, Any] = {"echo": False, "future": True}
    if not url.startswith("sqlite"):
        engine_kwargs.update({"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20})

    engine = create_async_engine(url, **engine_kwargs)
    if db_url is None:
        _global_engine = engine
        _global_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global session factory, initializing the engine if needed."""
    global _global_session_factory
    if _global_session_factory is None:
        get_async_engine()
    assert _global_session_factory is not None
    return _global_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependencies or background jobs."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
