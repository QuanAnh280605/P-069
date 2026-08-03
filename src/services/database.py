"""Database and Credential Encryption Services.

Provides:
  - Fernet encryption and decryption for target database connection URLs.
  - SQLAlchemy AsyncEngine and AsyncSession management for Metadata Store.
"""

import logging
from collections.abc import AsyncGenerator

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

logger = logging.getLogger(__name__)


def _get_fernet(key: str | None = None) -> Fernet:
    """Instantiate a Fernet cipher instance using provided key or settings."""
    if key:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    settings = get_settings()
    key_str = settings.encryption_key
    if key_str:
        try:
            return Fernet(key_str.encode("utf-8"))
        except Exception as exc:
            logger.warning("Invalid encryption_key in settings, using fallback: %s", exc)
    return Fernet(b"FiqLMBulPbTUShiUnFKXgt2OHpPv9Y3mBstowcTSKRc=")


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
    """Create and return a SQLAlchemy AsyncEngine instance."""
    url = db_url or get_settings().database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+"):
        parts = url.split("://", 1)
        url = f"postgresql+asyncpg://{parts[1]}"
    elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return create_async_engine(url, echo=False, future=True)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependencies or background jobs."""
    active_engine = get_async_engine()
    session_factory = async_sessionmaker(active_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
