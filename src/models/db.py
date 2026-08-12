"""SQLAlchemy 2.0 ORM Models for Metadata Store and User Authentication.

Includes tables:
  - users
  - user_sessions
  - semantic_databases
  - semantic_tables
  - semantic_columns
  - semantic_metrics
  - canonical_relationships
  - metric_versions
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="analyst")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    sessions: Mapped[list["UserSessionModel"]] = relationship(
        "UserSessionModel", back_populates="user", cascade="all, delete-orphan"
    )
    databases: Mapped[list["SemanticDatabaseModel"]] = relationship("SemanticDatabaseModel", back_populates="creator")
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
    tables: Mapped[list["SemanticTableModel"]] = relationship(
        "SemanticTableModel", back_populates="database", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["SemanticMetricModel"]] = relationship(
        "SemanticMetricModel", back_populates="database", cascade="all, delete-orphan"
    )
    relationships: Mapped[list["CanonicalRelationshipModel"]] = relationship(
        "CanonicalRelationshipModel", back_populates="database", cascade="all, delete-orphan"
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
    __table_args__ = (Index("idx_semantic_metrics_db_name", "db_id", "name"),)

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


class CanonicalRelationshipModel(Base):
    """Represents a canonical relationship between two semantic tables."""

    __tablename__ = "canonical_relationships"
    __table_args__ = (UniqueConstraint("connection_id", "from_entity_id", "to_entity_id", name="uq_canonical_rel"),)

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
