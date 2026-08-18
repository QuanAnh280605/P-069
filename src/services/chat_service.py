"""Persistence and authorization helpers for chat sessions and messages."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import (
    ChatMessageModel,
    ChatSessionModel,
    LiveTargetDbModel,
    SemanticDatabaseModel,
)

DEFAULT_SESSION_TITLE = "Cuộc trò chuyện mới"
ALLOWED_SENDERS = {"user", "assistant", "system"}


class ChatAuthorizationError(Exception):
    """Raised when a chat resource is missing or belongs to another user."""


async def get_chat_database(
    db: AsyncSession, user_id: int, db_id: int, require_live: bool = True
) -> SemanticDatabaseModel:
    """Return an owned semantic database and optionally require a live source."""
    stmt = select(SemanticDatabaseModel).where(
        SemanticDatabaseModel.id == db_id,
        SemanticDatabaseModel.created_by == user_id,
    )
    database = (await db.execute(stmt)).scalar_one_or_none()
    if database is None:
        raise ChatAuthorizationError("Chat database not found")
    if require_live and not await _has_live_source(db, db_id):
        raise ChatAuthorizationError("Chat is only supported for live databases")
    return database


async def _has_live_source(db: AsyncSession, db_id: int) -> bool:
    """Check whether a semantic database has a live target source."""
    stmt = select(LiveTargetDbModel.id).where(LiveTargetDbModel.semantic_db_id == db_id)
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def create_chat_session(db: AsyncSession, user_id: int, db_id: int, title: str | None = None) -> ChatSessionModel:
    """Create a chat session after validating database ownership."""
    await get_chat_database(db, user_id, db_id)
    session = ChatSessionModel(
        id=str(uuid.uuid4()),
        user_id=user_id,
        db_id=db_id,
        title=_normalize_title(title) if title else DEFAULT_SESSION_TITLE,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_chat_sessions(db: AsyncSession, user_id: int, db_id: int, limit: int = 50) -> list[ChatSessionModel]:
    """List owned sessions by most recently updated first."""
    await get_chat_database(db, user_id, db_id)
    safe_limit = min(max(limit, 1), 100)
    stmt = (
        select(ChatSessionModel)
        .options(selectinload(ChatSessionModel.messages))
        .where(ChatSessionModel.user_id == user_id, ChatSessionModel.db_id == db_id)
        .order_by(ChatSessionModel.updated_at.desc(), ChatSessionModel.id.desc())
        .limit(safe_limit)
    )
    return list((await db.execute(stmt)).scalars().unique().all())


async def get_chat_session_with_messages(db: AsyncSession, session_id: str, user_id: int) -> ChatSessionModel | None:
    """Load an owned session with messages ordered by sequence number."""
    stmt = (
        select(ChatSessionModel)
        .options(selectinload(ChatSessionModel.messages))
        .where(ChatSessionModel.id == session_id, ChatSessionModel.user_id == user_id)
    )
    return (await db.execute(stmt)).scalars().unique().one_or_none()


async def get_chat_session(db: AsyncSession, session_id: str, user_id: int) -> ChatSessionModel | None:
    """Load an owned session without eagerly loading its message history."""
    return await _get_owned_session(db, session_id, user_id)


async def get_chat_message_by_client_id(
    db: AsyncSession, session_id: str, client_message_id: str
) -> ChatMessageModel | None:
    """Find a message by its client id for idempotent request replay."""
    return await _find_client_message(db, session_id, client_message_id)


async def update_chat_session_title(
    db: AsyncSession, session_id: str, user_id: int, title: str
) -> ChatSessionModel | None:
    """Update an owned session title."""
    session = await _get_owned_session(db, session_id, user_id)
    if session is None:
        return None
    session.title = _normalize_title(title)
    session.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(session)
    return session


async def delete_chat_session(db: AsyncSession, session_id: str, user_id: int) -> bool:
    """Delete an owned session and its messages."""
    session = await _get_owned_session(db, session_id, user_id)
    if session is None:
        return False
    await db.delete(session)
    await db.commit()
    return True


async def save_chat_message(
    db: AsyncSession,
    session_id: str,
    sender: str,
    content: str,
    intent: str | None = None,
    metadata_json: dict | list | None = None,
    client_message_id: str | None = None,
) -> ChatMessageModel:
    """Persist a message and advance the session timestamp."""
    _validate_message(sender, content)
    session = await _get_session_for_update(db, session_id)
    if session is None:
        raise ChatAuthorizationError("Chat session not found")
    if client_message_id:
        existing = await _find_client_message(db, session_id, client_message_id)
        if existing is not None:
            return existing
    next_sequence = await _next_sequence(db, session_id)
    message = ChatMessageModel(
        id=str(uuid.uuid4()),
        session_id=session_id,
        client_message_id=client_message_id,
        sequence_no=next_sequence,
        sender=sender,
        content=content,
        intent=intent,
        metadata_json=metadata_json,
    )
    session.updated_at = datetime.now(UTC)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_recent_chat_history(db: AsyncSession, session_id: str, limit: int = 10) -> list[dict[str, str]]:
    """Return prior user and assistant messages in chronological order."""
    safe_limit = min(max(limit, 1), 50)
    stmt = (
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == session_id, ChatMessageModel.sender.in_(("user", "assistant")))
        .order_by(ChatMessageModel.sequence_no.desc())
        .limit(safe_limit)
    )
    messages = list((await db.execute(stmt)).scalars().all())
    messages.reverse()
    return [{"role": item.sender, "content": item.content} for item in messages]


async def get_chat_messages_page(
    db: AsyncSession,
    session_id: str,
    user_id: int,
    limit: int = 50,
    before_sequence: int | None = None,
) -> tuple[list[ChatMessageModel], int, int | None]:
    """Load one authorized message page and return count plus next cursor."""
    session = await _get_owned_session(db, session_id, user_id)
    if session is None:
        raise ChatAuthorizationError("Chat session not found")
    safe_limit = min(max(limit, 1), 100)
    conditions = [ChatMessageModel.session_id == session_id]
    if before_sequence is not None:
        conditions.append(ChatMessageModel.sequence_no < before_sequence)
    stmt = select(ChatMessageModel).where(*conditions).order_by(ChatMessageModel.sequence_no.desc()).limit(safe_limit)
    messages = list((await db.execute(stmt)).scalars().all())
    messages.reverse()
    count_stmt = select(func.count(ChatMessageModel.id)).where(ChatMessageModel.session_id == session_id)
    total = int((await db.execute(count_stmt)).scalar_one())
    next_cursor = messages[0].sequence_no if len(messages) == safe_limit and messages else None
    return messages, total, next_cursor


def auto_generate_session_title(first_message: str, max_length: int = 40) -> str:
    """Create a short readable title from the first user message."""
    normalized = re.sub(r"\s+", " ", first_message).strip()
    if not normalized:
        return DEFAULT_SESSION_TITLE
    return normalized[:max_length].rstrip() + ("..." if len(normalized) > max_length else "")


async def _get_owned_session(db: AsyncSession, session_id: str, user_id: int) -> ChatSessionModel | None:
    """Load a session while applying user ownership."""
    stmt = select(ChatSessionModel).where(ChatSessionModel.id == session_id, ChatSessionModel.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_session_for_update(db: AsyncSession, session_id: str) -> ChatSessionModel | None:
    """Load a session row for serialized sequence allocation."""
    stmt = select(ChatSessionModel).where(ChatSessionModel.id == session_id).with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_client_message(db: AsyncSession, session_id: str, client_message_id: str) -> ChatMessageModel | None:
    """Find a prior message for idempotent client retries."""
    stmt = select(ChatMessageModel).where(
        ChatMessageModel.session_id == session_id,
        ChatMessageModel.client_message_id == client_message_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _next_sequence(db: AsyncSession, session_id: str) -> int:
    """Allocate the next sequence while the session row is locked."""
    stmt = select(func.max(ChatMessageModel.sequence_no)).where(ChatMessageModel.session_id == session_id)
    current = (await db.execute(stmt)).scalar_one()
    return int(current or 0) + 1


def _normalize_title(title: str) -> str:
    """Normalize and validate a user-provided session title."""
    normalized = re.sub(r"\s+", " ", title).strip()
    if not normalized or len(normalized) > 255:
        raise ValueError("Session title must contain 1-255 characters")
    return normalized


def _validate_message(sender: str, content: str) -> None:
    """Validate message fields before writing them."""
    if sender not in ALLOWED_SENDERS:
        raise ValueError("Invalid chat message sender")
    if not content.strip():
        raise ValueError("Chat message content cannot be empty")
