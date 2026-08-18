"""enforce Workspace ownership for semantic databases"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "k6l7m8n9o0"
down_revision: str | Sequence[str] | None = "j5k6l7m8n9o0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require every semantic database to belong to a Workspace."""
    bind = op.get_bind()
    missing = bind.execute(
        sa.text("SELECT COUNT(*) FROM semantic_databases WHERE org_id IS NULL")
    ).scalar_one()
    if missing:
        raise RuntimeError("Cannot enforce Workspace ownership while semantic_databases.org_id contains NULL values")
    op.alter_column("semantic_databases", "org_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    """Restore nullable ownership for rollback compatibility."""
    op.alter_column("semantic_databases", "org_id", existing_type=sa.Integer(), nullable=True)
