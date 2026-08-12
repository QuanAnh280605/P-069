"""add semantic_db_id to imported_schemas and live_target_databases

Revision ID: f1a2b3c4d5e6
Revises: b3c4d5e6f789
Create Date: 2026-08-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "b3c4d5e6f789"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    if _column_exists("imported_schemas", "semantic_db_id"):
        return
    op.add_column(
        "imported_schemas",
        sa.Column("semantic_db_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_imported_schemas_semantic_db_id",
        "imported_schemas",
        "semantic_databases",
        ["semantic_db_id"],
        ["id"],
        ondelete="SET NULL",
    )
    if not _column_exists("live_target_databases", "semantic_db_id"):
        op.add_column(
            "live_target_databases",
            sa.Column("semantic_db_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_live_target_dbs_semantic_db_id",
            "live_target_databases",
            "semantic_databases",
            ["semantic_db_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema."""
    if _column_exists("live_target_databases", "semantic_db_id"):
        op.drop_constraint("fk_live_target_dbs_semantic_db_id", "live_target_databases", type_="foreignkey")
        op.drop_column("live_target_databases", "semantic_db_id")
    if _column_exists("imported_schemas", "semantic_db_id"):
        op.drop_constraint("fk_imported_schemas_semantic_db_id", "imported_schemas", type_="foreignkey")
        op.drop_column("imported_schemas", "semantic_db_id")


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    columns = sa.inspect(bind).get_columns(table)
    return any(col["name"] == column for col in columns)
