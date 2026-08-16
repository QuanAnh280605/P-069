"""initial_schema

Revision ID: a22b27560724
Revises:
Create Date: 2026-08-04 15:09:16.166454

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a22b27560724"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    if bind is None:
        return False
    try:
        insp = sa.inspect(bind)
        return table_name in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("role", sa.String(length=50), nullable=False, server_default="analyst"),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
            sa.UniqueConstraint("username"),
        )
        op.create_index("idx_users_email", "users", ["email"], unique=True)
        op.create_index("idx_users_username", "users", ["username"], unique=True)

    if not _table_exists("user_sessions"):
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("refresh_token_hash"),
        )
        op.create_index("idx_user_sessions_user", "user_sessions", ["user_id"])
        op.create_index("idx_user_sessions_token", "user_sessions", ["refresh_token_hash"])

    if not _table_exists("semantic_databases"):
        op.create_table(
            "semantic_databases",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("db_type", sa.String(length=50), nullable=False),
            sa.Column("conn_url_enc", sa.String(length=500), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("semantic_tables"):
        op.create_table(
            "semantic_tables",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("db_id", sa.Integer(), nullable=False),
            sa.Column("table_name", sa.String(length=200), nullable=False),
            sa.Column("business_name", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["db_id"], ["semantic_databases.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("semantic_columns"):
        op.create_table(
            "semantic_columns",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("table_id", sa.Integer(), nullable=False),
            sa.Column("column_name", sa.String(length=200), nullable=False),
            sa.Column("data_type", sa.String(length=100), nullable=False),
            sa.Column("business_name", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("is_primary_key", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_foreign_key", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_nullable", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("fk_target_table", sa.String(length=200), nullable=True),
            sa.Column("fk_target_column", sa.String(length=200), nullable=True),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["table_id"], ["semantic_tables.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("semantic_metrics"):
        op.create_table(
            "semantic_metrics",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("db_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("sql_template", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="pending_approval"),
            sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["db_id"], ["semantic_databases.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    pass

