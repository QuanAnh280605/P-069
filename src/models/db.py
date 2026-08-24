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
  - dashboard_layouts
"""

from datetime import datetime
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db_base import Base, utc_now
from src.models.db_chat import ChatMessageModel, ChatSessionModel
from src.models.review_mixin import REVIEW_STATUS_CHECK, ReviewStateMixin

__all__ = [
    "Base",
    "CanonicalRelationshipModel",
    "ChatMessageModel",
    "ChatSessionModel",
    "DashboardLayoutModel",
    "ImportedSchemaModel",
    "LiveTargetDbModel",
    "MetricVersionModel",
    "OrganizationAuditLogModel",
    "OrganizationInvitationModel",
    "OrganizationMemberModel",
    "OrganizationModel",
    "SemanticColumnModel",
    "SemanticDatabaseModel",
    "SemanticMetricModel",
    "SemanticTableModel",
    "UserModel",
    "UserSessionModel",
    "utc_now",
]


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
    imported_schemas: Mapped[list["ImportedSchemaModel"]] = relationship(
        "ImportedSchemaModel", back_populates="creator", cascade="all, delete-orphan"
    )
    live_target_dbs: Mapped[list["LiveTargetDbModel"]] = relationship(
        "LiveTargetDbModel", back_populates="creator", cascade="all, delete-orphan"
    )
    created_metrics: Mapped[list["SemanticMetricModel"]] = relationship(
        "SemanticMetricModel", back_populates="creator", foreign_keys="SemanticMetricModel.created_by"
    )
    created_tables: Mapped[list["SemanticTableModel"]] = relationship(
        "SemanticTableModel", back_populates="creator", foreign_keys="SemanticTableModel.created_by"
    )
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
    dashboard_layout: Mapped["DashboardLayoutModel | None"] = relationship(
        "DashboardLayoutModel", back_populates="database", cascade="all, delete-orphan", uselist=False
    )


class SemanticTableModel(ReviewStateMixin, Base):
    """Metadata Store representation of an enriched database table."""

    __tablename__ = "semantic_tables"
    __table_args__ = (
        UniqueConstraint("db_id", "table_name", name="uq_semantic_tables_db_table"),
        CheckConstraint(REVIEW_STATUS_CHECK, name="ck_semantic_tables_review_status"),
        Index("idx_semantic_tables_db_review", "db_id", "review_status"),
    )

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
    creator: Mapped["UserModel | None"] = relationship(
        "UserModel", back_populates="created_tables", foreign_keys=[created_by]
    )
    reviewer: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys="SemanticTableModel.reviewed_by")
    editor: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys="SemanticTableModel.updated_by")
    columns: Mapped[list["SemanticColumnModel"]] = relationship(
        "SemanticColumnModel", back_populates="table", cascade="all, delete-orphan"
    )


class SemanticColumnModel(ReviewStateMixin, Base):
    """Metadata Store representation of an enriched database column."""

    __tablename__ = "semantic_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "column_name", name="uq_semantic_columns_table_col"),
        CheckConstraint(REVIEW_STATUS_CHECK, name="ck_semantic_columns_review_status"),
        Index("idx_semantic_columns_table_review", "table_id", "review_status"),
    )

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
    reviewer: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys="SemanticColumnModel.reviewed_by")
    editor: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys="SemanticColumnModel.updated_by")


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
    """Immutable version history for a semantic metric definition.

    Rows are append-only: an edit to a published metric creates a new
    ``pending_approval`` row while the live ``semantic_metrics`` row keeps
    serving the last approved definition until the draft is promoted.
    """

    __tablename__ = "metric_versions"
    __table_args__ = (
        Index("idx_metric_versions_metric_version", "metric_id", "version"),
        UniqueConstraint("metric_id", "version", name="uq_metric_versions_metric_version"),
        CheckConstraint(
            "status IN ('pending_approval', 'needs_review', 'approved', 'superseded', 'rejected')",
            name="ck_metric_versions_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semantic_metrics.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    parent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    metric: Mapped["SemanticMetricModel"] = relationship("SemanticMetricModel", back_populates="versions")
    changer: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys=[changed_by])
    approver: Mapped["UserModel | None"] = relationship("UserModel", foreign_keys=[approved_by])


class DashboardLayoutModel(Base):
    """Singleton visual dashboard layout owned by one Semantic Database workspace."""

    __tablename__ = "dashboard_layouts"
    __table_args__ = (UniqueConstraint("db_id", name="uq_dashboard_layouts_db_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    db_id: Mapped[int] = mapped_column(Integer, ForeignKey("semantic_databases.id", ondelete="CASCADE"), nullable=False)
    layout_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    database: Mapped["SemanticDatabaseModel"] = relationship("SemanticDatabaseModel", back_populates="dashboard_layout")
    updater: Mapped["UserModel | None"] = relationship("UserModel")
