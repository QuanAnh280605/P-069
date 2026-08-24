"""Merge foreign-key metadata and workspace migration heads.

Revision ID: p2q3r4s5t6u
Revises: n9o0p1q2r3s, o1p2q3r4s5t6
Create Date: 2026-08-24
"""

from collections.abc import Sequence

revision: str = "p2q3r4s5t6u"
down_revision: tuple[str, str] = ("n9o0p1q2r3s", "o1p2q3r4s5t6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge independent revisions without changing the schema."""


def downgrade() -> None:
    """Keep the merge point reversible without changing the schema."""
