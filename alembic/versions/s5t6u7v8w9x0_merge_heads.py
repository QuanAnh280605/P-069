"""Merge dashboard layouts and schema sync logs heads.

Revision ID: s5t6u7v8w9x0
Revises: 95ff234b973e, r4s5t6u7v8w9
Create Date: 2026-08-24
"""

from collections.abc import Sequence

revision: str = "s5t6u7v8w9x0"
down_revision: str | Sequence[str] | None = ("95ff234b973e", "r4s5t6u7v8w9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge point — no schema changes needed."""


def downgrade() -> None:
    """Merge point — no schema changes needed."""
