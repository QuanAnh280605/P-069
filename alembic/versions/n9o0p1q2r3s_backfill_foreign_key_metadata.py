"""Backfill persisted foreign-key metadata from canonical relationships."""

from collections.abc import Sequence

from alembic import op

revision: str = "n9o0p1q2r3s"
down_revision: str | Sequence[str] | None = "m8n9o0p1q2r"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rebuild FK flags without accessing target databases."""
    op.execute(
        """
        UPDATE semantic_columns AS source
        SET is_foreign_key = TRUE,
            fk_target_table = target_table.table_name,
            fk_target_column = target.column_name
        FROM canonical_relationships AS relationship
        CROSS JOIN LATERAL jsonb_array_elements(relationship.column_pairs::jsonb) AS pair
        JOIN semantic_columns AS target ON target.id = (pair->>'to_column_id')::integer
        JOIN semantic_tables AS target_table ON target_table.id = target.table_id
        WHERE source.id = (pair->>'from_column_id')::integer
          AND relationship.validation_status = 'valid'
        """
    )


def downgrade() -> None:
    """Leave backfilled metadata in place because it is non-destructive."""
