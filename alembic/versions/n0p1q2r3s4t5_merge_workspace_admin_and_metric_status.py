"""Merge workspace admin role and metric status constraint heads.

Revision ID: n0p1q2r3s4t5
Revises: m8n9o0p1q2r3, m9n0p1q2r3s4
Create Date: 2026-08-22
"""

from collections.abc import Sequence

revision: str = "n0p1q2r3s4t5"
down_revision: str | Sequence[str] | None = ("m8n9o0p1q2r3", "m9n0p1q2r3s4")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge point — no schema changes needed."""


def downgrade() -> None:
    """Merge point — no schema changes needed."""
