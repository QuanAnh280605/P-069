"""Merge dashboard/hitl review and foreign key heads.

Revision ID: q3r4s5t6u7v8
Revises: fb92d622f1e0, p2q3r4s5t6u
Create Date: 2026-08-25 10:41:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "q3r4s5t6u7v8"
down_revision: tuple[str, str] = ("fb92d622f1e0", "p2q3r4s5t6u")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge independent revisions without changing the schema."""
    pass


def downgrade() -> None:
    """Keep the merge revision reversible without changing schema."""
    pass
