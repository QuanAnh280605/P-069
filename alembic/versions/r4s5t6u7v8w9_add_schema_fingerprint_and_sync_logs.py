"""Add schema_fingerprint and sync logs for daily auto-sync and self-healing.

Revision ID: r4s5t6u7v8w9
Revises: q3r4s5t6u7v8
Create Date: 2026-08-24 20:53:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "r4s5t6u7v8w9"
down_revision: str | Sequence[str] | None = "q3r4s5t6u7v8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add fingerprint and sync status columns to semantic_databases and create schema_sync_logs table."""
    conn = op.get_bind()
    insp = sa.inspect(conn)

    existing_cols = {col["name"] for col in insp.get_columns("semantic_databases")}
    with op.batch_alter_table("semantic_databases") as batch:
        if "schema_fingerprint" not in existing_cols:
            batch.add_column(sa.Column("schema_fingerprint", sa.String(length=64), nullable=True))
        if "last_synced_at" not in existing_cols:
            batch.add_column(sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
        if "sync_status" not in existing_cols:
            batch.add_column(
                sa.Column("sync_status", sa.String(length=50), nullable=False, server_default="synced")
            )

    tables = set(insp.get_table_names())
    if "schema_sync_logs" not in tables:
        op.create_table(
            "schema_sync_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("semantic_db_id", sa.Integer(), nullable=False),
            sa.Column("live_db_id", sa.Integer(), nullable=True),
            sa.Column("trigger_type", sa.String(length=50), nullable=False, server_default="instant_check"),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="success"),
            sa.Column("old_fingerprint", sa.String(length=64), nullable=True),
            sa.Column("new_fingerprint", sa.String(length=64), nullable=True),
            sa.Column("changes_summary", sa.JSON(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "trigger_type IN ('cron', 'instant_check', 'manual')",
                name="ck_schema_sync_logs_trigger_type",
            ),
            sa.CheckConstraint(
                "status IN ('success', 'healed', 'no_change', 'failed')",
                name="ck_schema_sync_logs_status",
            ),
            sa.ForeignKeyConstraint(["semantic_db_id"], ["semantic_databases.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["live_db_id"], ["live_target_databases.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_schema_sync_logs_db_created",
            "schema_sync_logs",
            ["semantic_db_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    """Drop schema_sync_logs table and sync columns from semantic_databases."""
    op.drop_index("idx_schema_sync_logs_db_created", table_name="schema_sync_logs")
    op.drop_table("schema_sync_logs")

    with op.batch_alter_table("semantic_databases") as batch:
        batch.drop_column("sync_status")
        batch.drop_column("last_synced_at")
        batch.drop_column("schema_fingerprint")
