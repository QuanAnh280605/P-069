"""add canonical semantic layer tables

Revision ID: b3c4d5e6f789
Revises: e7f123456789
Create Date: 2026-08-11 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f789"
down_revision: str | Sequence[str] | None = "e7f123456789"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Expand semantic_tables ---
    op.add_column("semantic_tables", sa.Column("physical_schema", sa.String(length=200), nullable=True))
    op.add_column("semantic_tables", sa.Column("primary_key_column", sa.String(length=200), nullable=True))
    op.add_column("semantic_tables", sa.Column("created_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_semantic_tables_created_by_users",
        "semantic_tables",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- Expand semantic_columns ---
    op.add_column("semantic_columns", sa.Column("is_time_dimension", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("semantic_columns", sa.Column("allowed_values", sa.JSON(), nullable=True))

    # --- Expand semantic_metrics ---
    op.add_column("semantic_metrics", sa.Column("base_entity_id", sa.Integer(), nullable=True))
    op.add_column("semantic_metrics", sa.Column("formula", sa.Text(), nullable=False, server_default=""))
    op.add_column("semantic_metrics", sa.Column("aggregation_type", sa.String(length=50), nullable=True))
    op.add_column("semantic_metrics", sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))
    op.add_column("semantic_metrics", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_semantic_metrics_base_entity_tables",
        "semantic_metrics",
        "semantic_tables",
        ["base_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_semantic_metrics_approved_by_users",
        "semantic_metrics",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "semantic_metrics",
        "status",
        server_default="draft",
    )

    # --- Create canonical_relationships ---
    if not _table_exists("canonical_relationships"):
        op.create_table(
            "canonical_relationships",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("connection_id", sa.Integer(), nullable=False),
            sa.Column("from_entity_id", sa.Integer(), nullable=False),
            sa.Column("to_entity_id", sa.Integer(), nullable=False),
            sa.Column("relationship_type", sa.String(length=50), nullable=False),
            sa.Column("join_condition", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["connection_id"], ["semantic_databases.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["from_entity_id"], ["semantic_tables.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["to_entity_id"], ["semantic_tables.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "connection_id", "from_entity_id", "to_entity_id", name="uq_canonical_rel"
            ),
        )

    # --- Create metric_versions ---
    if not _table_exists("metric_versions"):
        op.create_table(
            "metric_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("metric_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("formula", sa.Text(), nullable=False),
            sa.Column("changed_by", sa.Integer(), nullable=True),
            sa.Column("change_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["metric_id"], ["semantic_metrics.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_metric_versions_metric_version",
            "metric_versions",
            ["metric_id", "version"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    # --- Drop metric_versions ---
    if _table_exists("metric_versions"):
        op.drop_index("ix_metric_versions_metric_version", table_name="metric_versions")
        op.drop_table("metric_versions")

    # --- Drop canonical_relationships ---
    if _table_exists("canonical_relationships"):
        op.drop_table("canonical_relationships")

    # --- Revert semantic_metrics ---
    op.drop_constraint("fk_semantic_metrics_approved_by_users", "semantic_metrics", type_="foreignkey")
    op.drop_constraint("fk_semantic_metrics_base_entity_tables", "semantic_metrics", type_="foreignkey")
    op.drop_column("semantic_metrics", "approved_by")
    op.drop_column("semantic_metrics", "version")
    op.drop_column("semantic_metrics", "aggregation_type")
    op.drop_column("semantic_metrics", "formula")
    op.drop_column("semantic_metrics", "base_entity_id")
    op.alter_column("semantic_metrics", "status", server_default="active")

    # --- Revert semantic_columns ---
    op.drop_column("semantic_columns", "allowed_values")
    op.drop_column("semantic_columns", "is_time_dimension")

    # --- Revert semantic_tables ---
    op.drop_constraint("fk_semantic_tables_created_by_users", "semantic_tables", type_="foreignkey")
    op.drop_column("semantic_tables", "created_by")
    op.drop_column("semantic_tables", "primary_key_column")
    op.drop_column("semantic_tables", "physical_schema")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)
