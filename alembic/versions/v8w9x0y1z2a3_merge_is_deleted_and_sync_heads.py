"""Merge is_deleted and schema sync heads into a single linear head.

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2, s5t6u7v8w9x0
Create Date: 2026-08-26

This migration only reconciles the Alembic revision graph. It performs no
schema mutations so it is safe to apply on databases where either branch was
already stamped.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "v8w9x0y1z2a3"
down_revision: tuple[str, str] = ("u7v8w9x0y1z2", "s5t6u7v8w9x0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge independent revisions without changing the schema."""
    pass


def downgrade() -> None:
    """Keep the merge revision reversible without changing schema."""
    pass
