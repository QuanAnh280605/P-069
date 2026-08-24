"""Declarative base and shared column helpers for all ORM models."""

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)
