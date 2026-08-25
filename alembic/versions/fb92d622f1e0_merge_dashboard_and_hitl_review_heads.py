"""Merge dashboard and hitl review heads.

Revision ID: fb92d622f1e0
Revises: 95ff234b973e, p2q3r4s5t6u7
Create Date: 2026-08-24 20:42:04.647294

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "fb92d622f1e0"
down_revision: str | Sequence[str] | None = ("95ff234b973e", "p2q3r4s5t6u7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
