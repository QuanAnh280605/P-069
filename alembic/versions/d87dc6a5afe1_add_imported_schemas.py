"""add imported schemas

Revision ID: d87dc6a5afe1
Revises: a22b27560724
Create Date: 2026-08-05 19:15:04.277233

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d87dc6a5afe1"
down_revision: str | Sequence[str] | None = "a22b27560724"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    if _table_exists():
        return
    op.create_table(
        "imported_schemas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("dialect", sa.String(length=50), nullable=False),
        sa.Column("schema_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_imported_schemas_owner_updated",
        "imported_schemas",
        ["created_by", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    if not _table_exists():
        return
    op.drop_index("idx_imported_schemas_owner_updated", table_name="imported_schemas")
    op.drop_table("imported_schemas")


def _table_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table("imported_schemas")
