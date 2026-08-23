"""Drop the obsolete account-level user role.

Revision ID: o1p2q3r4s5t6
Revises: n0p1q2r3s4t5
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: str | Sequence[str] | None = "n0p1q2r3s4t5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove the obsolete users.role column."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")


def downgrade() -> None:
    """Restore a non-authoritative legacy role for rollback compatibility."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=50), nullable=True, server_default="analyst"))
