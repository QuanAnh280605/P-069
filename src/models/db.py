"""SQLAlchemy 2.0 ORM Models for Metadata Store and User Authentication.

Includes tables:
  - users
  - user_sessions
  - organizations
  - organization_members
  - organization_invitations
  - organization_audit_logs
  - semantic_databases
  - semantic_tables
  - semantic_columns
  - semantic_metrics
  - canonical_relationships
  - metric_versions
  - chat_sessions
  - chat_messages
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class OrganizationModel(Base):
    """Company Workspace that owns semantic-layer resources."""

    __tablename__ = "organizations"
    __table_args__ = (Index("idx_organizations_slug", "slug", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    creator: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys=[created_by])
    members: Mapped[list["OrganizationMemberModel"]] = relationship(
        "OrganizationMemberModel", back_populates="organization", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["OrganizationInvitationModel"]] = relationship(
        "OrganizationInvitationModel", back_populates="organization", cascade="all, delete-orphan"
    )
    semantic_databases: Mapped[list["SemanticDatabaseModel"]] = relationship(
        "SemanticDatabaseModel", back_populates="organization"
    )


class OrganizationMemberModel(Base):
    """User membership and role inside a Workspace."""

    __tablename__ = "organization_members"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'data_lead', 'member')", name="ck_organization_members_role"),
        UniqueConstraint("org_id", "user_id", name="uq_organization_members_org_user"),
        Index("idx_organization_members_org_role", "org_id", "role"),
        Index("idx_organization_members_user_org", "user_id", "org_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel", back_populates="members")
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="organization_memberships")


class OrganizationInvitationModel(Base):
    """One-time Workspace invitation represented by a hashed token."""

    __tablename__ = "organization_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'data_lead', 'member')", name="ck_organization_invitations_role"),
        Index("idx_organization_invitations_org_status", "org_id", "status"),
        Index("idx_organization_invitations_token_hash", "token_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    inviter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    invitee_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    accepted_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel", back_populates="invitations")


class OrganizationAuditLogModel(Base):
    """Audit trail for Workspace membership and invitation mutations."""

    __tablename__ = "organization_audit_logs"
    __table_args__ = (Index("idx_organization_audit_logs_org_created", "org_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    target_invitation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organization_invitations.id", ondelete="SET NULL")
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class UserModel(Base):
    """User account model for authentication and RBAC authorization."""

    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email", unique=True),
        Index("idx_users_username", "username", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    sessions: Mapped[list["UserSessionModel"]] = relationship(
        "UserSessionModel", back_populates="user", cascade="all, delete-orphan"
    )
    databases: Mapped[list["SemanticDatabaseModel"]] = relationship("SemanticDatabaseModel", back_populates="creator")
    chat_sessions: Mapped[list["ChatSessionModel"]] = relationship(
        "ChatSessionModel", back_populates="user", cascade="all, delete-orphan"
    )
    metric_requests: Mapped[list["MetricRequestModel"]] = relationship(
        "MetricRequestModel", back_populates="requester", foreign_keys="MetricRequestModel.requester_id"
    )
    notifications: Mapped[list["NotificationModel"]] = relationship(
        "NotificationModel", back_populates="recipient", cascade="all, delete-orphan"
    )
    imported_schemas: Mapped[list["ImportedSchemaModel"]] = relationship(
        "ImportedSchemaModel", back_populates="creator", cascade="all, delete-orphan"
    )
    live_target_dbs: Mapped[list["LiveTargetDbModel"]] = relationship(
        "LiveTargetDbModel", back_populates="creator", cascade="all, delete-orphan"
    )
    created_metrics: Mapped[list["SemanticMetricModel"]] = relationship(
        "SemanticMetricModel", back_populates="creator", foreign_keys="SemanticMetricModel.created_by"
    )
    created_tables: Mapped[list["SemanticTableModel"]] = relationship("SemanticTableModel", back_populates="creator")
    approved_metrics: Mapped[list["SemanticMetricModel"]] = relationship(
        "SemanticMetricModel", back_populates="approver", foreign_keys="SemanticMetricModel.approved_by"
    )
    organization_memberships: Mapped[list["OrganizationMemberModel"]] = relationship(
        "OrganizationMemberModel", back_populates="user", cascade="all, delete-orphan"
    )


class UserSessionModel(Base):
    """User login session and refresh token tracking model."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_user_sessions_user", "user_id"),
        Index("idx_user_sessions_token", "refresh_token_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="sessions")


class ImportedSchemaModel(Base):
    """Persisted technical schema metadata imported from an SQL dump."""

    __tablename__ = "imported_schemas"
    __table_args__ = (Index("idx_imported_schemas_owner_updated", "created_by", "updated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dialect: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    semantic_db_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("semantic_databases.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    creator: Mapped["UserModel"] = relationship("UserModel", back_populates="imported_schemas")
    semantic_database: Mapped["SemanticDatabaseModel | None"] = relationship("SemanticDatabaseModel")


class LiveTargetDbModel(Base):
    """Persisted technical schema metadata introspected from a live target database."""

    __tablename__ = "live_target_databases"
    __table_args__ = (Index("idx_live_target_dbs_owner_updated", "created_by", "updated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dialect: Mapped[str] = mapped_column(String(50), nullable=False)
    conn_url_enc: Mapped[str] = mapped_column(Text, nullable=False)
    schema_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    semantic_db_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("semantic_databases.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    creator: Mapped["UserModel"] = relationship("UserModel", back_populates="live_target_dbs")
    semantic_database: Mapped["SemanticDatabaseModel | None"] = relationship("SemanticDatabaseModel")


class SemanticDatabaseModel(Base):
    """Metadata Store representation of a target database."""

    __tablename__ = "semantic_databases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)
    conn_url_enc: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    creator: Mapped["UserModel | None"] = relationship("UserModel", back_populates="databases")
    organization: Mapped["OrganizationModel | None"] = relationship(
        "OrganizationModel", back_populates="semantic_databases"
    )
    tables: Mapped[list["SemanticTableModel"]] = relationship(
        "SemanticTableModel", back_populates="database", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["SemanticMetricModel"]] = relationship(
        "SemanticMetricModel", back_populates="database", cascade="all, delete-orphan"
    )
    relationships: Mapped[list["CanonicalRelationshipModel"]] = relationship(
        "CanonicalRelationshipModel", back_populates="database", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSessionModel"]] = relationship(
        "ChatSessionModel", back_populates="database", cascade="all, delete-orphan"
    )
    metric_requests: Mapped[list["MetricRequestModel"]] = relationship(
        "MetricRequestModel", back_populates="database", cascade="all, delete-orphan"
    )


class SemanticTableModel(Base):
    """Metadata Store representation of an enriched database table."""

    __tablename__ = "semantic_tables"
    __table_args__ = (UniqueConstraint("db_id", "table_name", name="uq_semantic_tables_db_table"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    db_id: Mapped[int] = mapped_column(Integer, ForeignKey("semantic_databases.id", ondelete="CASCADE"), nullable=False)
    table_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    row_count_approx: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    physical_schema: Mapped[str | None] = mapped_column(String(200), nullable=True)
    primary_key_column: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    database: Mapped["SemanticDatabaseModel"] = relationship("SemanticDatabaseModel", back_populates="tables")
    creator: Mapped["UserModel | None"] = relationship("UserModel", back_populates="created_tables")
    columns: Mapped[list["SemanticColumnModel"]] = relationship(
        "SemanticColumnModel", back_populates="table", cascade="all, delete-orphan"
    )


class SemanticColumnModel(Base):
    """Metadata Store representation of an enriched database column."""

    __tablename__ = "semantic_columns"
    __table_args__ = (UniqueConstraint("table_id", "column_name", name="uq_semantic_columns_table_col"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey("semantic_tables.id", ondelete="CASCADE"), nullable=False)
    column_name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_primary_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fk_target_table: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fk_target_column: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_time_dimension: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    table: Mapped["SemanticTableModel"] = relationship("SemanticTableModel", back_populates="columns")


class SemanticMetricModel(Base):
    """Metadata Store representation of a business metric."""

    __tablename__ = "semantic_metrics"
    __table_args__ = (
        Index("idx_semantic_metrics_db_name", "db_id", "name"),
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'needs_review', 'approved', 'unverified')",
            name="ck_semantic_metrics_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    db_id: Mapped[int] = mapped_column(Integer, ForeignKey("semantic_databases.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sql_template: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    base_entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("semantic_tables.id", ondelete="SET NULL"), nullable=True
    )
    formula: Mapped[str] = mapped_column(Text, nullable=False, default="")
    aggregation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    database: Mapped["SemanticDatabaseModel"] = relationship("SemanticDatabaseModel", back_populates="metrics")
    creator: Mapped["UserModel | None"] = relationship(
        "UserModel", back_populates="created_metrics", foreign_keys=[created_by]
    )
    base_entity: Mapped["SemanticTableModel | None"] = relationship("SemanticTableModel")
    approver: Mapped["UserModel | None"] = relationship(
        "UserModel", back_populates="approved_metrics", foreign_keys=[approved_by]
    )
    versions: Mapped[list["MetricVersionModel"]] = relationship(
        "MetricVersionModel", back_populates="metric", cascade="all, delete-orphan"
    )


def _relationship_key_default(context: Any) -> str:
    """Build a deterministic relationship identity for direct ORM callers."""
    parameters = context.get_current_parameters()
    return ":".join(str(parameters.get(name, "")) for name in ("from_entity_id", "join_condition", "to_entity_id"))


class CanonicalRelationshipModel(Base):
    """Represents a canonical relationship between two semantic tables."""

    __tablename__ = "canonical_relationships"
    __table_args__ = (UniqueConstraint("connection_id", "relationship_key", name="uq_canonical_rel_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semantic_databases.id", ondelete="CASCADE"), nullable=False
    )
    from_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semantic_tables.id", ondelete="CASCADE"), nullable=False
    )
    to_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semantic_tables.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    join_condition: Mapped[str] = mapped_column(Text, nullable=False)
    relationship_key: Mapped[str] = mapped_column(String(500), nullable=False, default=_relationship_key_default)
    constraint_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    column_pairs: Mapped[list[dict[str, int]]] = mapped_column(JSON, nullable=False, default=list)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    database: Mapped["SemanticDatabaseModel"] = relationship("SemanticDatabaseModel", back_populates="relationships")
    from_entity: Mapped["SemanticTableModel"] = relationship("SemanticTableModel", foreign_keys=[from_entity_id])
    to_entity: Mapped["SemanticTableModel"] = relationship("SemanticTableModel", foreign_keys=[to_entity_id])


class MetricVersionModel(Base):
    """Version history for a semantic metric formula."""

    __tablename__ = "metric_versions"
    __table_args__ = (Index("idx_metric_versions_metric_version", "metric_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semantic_metrics.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    metric: Mapped["SemanticMetricModel"] = relationship("SemanticMetricModel", back_populates="versions")
    changer: Mapped["UserModel | None"] = relationship("UserModel")


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

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="chat_sessions")
    database: Mapped["SemanticDatabaseModel"] = relationship("SemanticDatabaseModel", back_populates="chat_sessions")
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


class MetricRequestModel(Base):
    """A Member-submitted proposal awaiting Data Lead review."""

    __tablename__ = "metric_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_metric_requests_status"),
        Index("idx_metric_requests_db_status", "db_id", "status"),
        Index("idx_metric_requests_requester", "requester_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    db_id: Mapped[int] = mapped_column(Integer, ForeignKey("semantic_databases.id", ondelete="CASCADE"), nullable=False)
    requester_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assistant_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    suggestion_index: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("semantic_metrics.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    database: Mapped["SemanticDatabaseModel"] = relationship("SemanticDatabaseModel", back_populates="metric_requests")
    requester: Mapped["UserModel"] = relationship(
        "UserModel", back_populates="metric_requests", foreign_keys=[requester_id]
    )
    metric: Mapped["SemanticMetricModel | None"] = relationship("SemanticMetricModel")


class NotificationModel(Base):
    """Persistent in-app notification for a Workspace user."""

    __tablename__ = "notifications"
    __table_args__ = (Index("idx_notifications_recipient_unread", "recipient_id", "read_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metric_request_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("metric_requests.id", ondelete="CASCADE"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    recipient: Mapped["UserModel"] = relationship("UserModel", back_populates="notifications")
    metric_request: Mapped["MetricRequestModel | None"] = relationship("MetricRequestModel")
