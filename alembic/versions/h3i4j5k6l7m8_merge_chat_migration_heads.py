"""merge existing semantic schema head with chat persistence head

Revision ID: h3i4j5k6l7m8
Revises: d9e0f1a2b3c4, g2h3i4j5k6l7
Create Date: 2026-08-18 20:30:00.000000
"""

from collections.abc import Sequence

revision: str = "h3i4j5k6l7m8"
down_revision: tuple[str, str] = ("d9e0f1a2b3c4", "g2h3i4j5k6l7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge migration branches without changing schema."""
    pass


def downgrade() -> None:
    """Keep the merge revision reversible without changing schema."""
    pass
