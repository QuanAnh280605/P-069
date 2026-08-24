"""Chat persistence models: sessions and messages."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db_base import Base, utc_now


class ChatSessionModel(Base):
    """A persisted conversation owned by one user and semantic database."""

    __tablename__ = "chat_sessions"
    __table_args__ = (Index("idx_chat_sessions_user_db", "user_id", "db_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    db_id: Mapped[int] = mapped_column(Integer, ForeignKey("semantic_databases.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Cuộc trò chuyện mới")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="chat_sessions")  # noqa: F821
    database: Mapped["SemanticDatabaseModel"] = relationship(  # noqa: F821
        "SemanticDatabaseModel", back_populates="chat_sessions"
    )
    messages: Mapped[list["ChatMessageModel"]] = relationship(
        "ChatMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageModel.sequence_no",
    )


class ChatMessageModel(Base):
    """One user, assistant, or system message in a chat session."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
        UniqueConstraint("session_id", "client_message_id", name="uq_chat_messages_session_client_id"),
        UniqueConstraint("session_id", "sequence_no", name="uq_chat_messages_session_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    client_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sender: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    session: Mapped["ChatSessionModel"] = relationship("ChatSessionModel", back_populates="messages")
