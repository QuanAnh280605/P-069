"""add live target databases

Revision ID: e7f123456789
Revises: d87dc6a5afe1
Create Date: 2026-08-05 20:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f123456789"
down_revision: str | Sequence[str] | None = "d87dc6a5afe1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    if _table_exists():
        return
    op.create_table(
        "live_target_databases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("dialect", sa.String(length=50), nullable=False),
        sa.Column("conn_url_enc", sa.Text(), nullable=False),
        sa.Column("schema_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_live_target_dbs_owner_updated",
        "live_target_databases",
        ["created_by", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    if not _table_exists():
        return
    op.drop_index("idx_live_target_dbs_owner_updated", table_name="live_target_databases")
    op.drop_table("live_target_databases")


def _table_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table("live_target_databases")
