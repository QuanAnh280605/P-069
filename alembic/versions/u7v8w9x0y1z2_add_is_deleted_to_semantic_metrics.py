"""Add is_deleted column to semantic_metrics for soft delete support."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "u7v8w9x0y1z2"
down_revision: str | Sequence[str] | None = "q3r4s5t6u7v8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_deleted column with default False."""
    with op.batch_alter_table("semantic_metrics") as batch:
        batch.add_column(
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0" if op.get_bind().dialect.name == "sqlite" else "false"))
        )


def downgrade() -> None:
    """Drop is_deleted column from semantic_metrics."""
    with op.batch_alter_table("semantic_metrics") as batch:
        batch.drop_column("is_deleted")
