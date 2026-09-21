"""add relationship review metadata

Revision ID: w1x2y3z4a5b6
Revises: v8w9x0y1z2a3
Create Date: 2026-08-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "w1x2y3z4a5b6"
down_revision: str | Sequence[str] | None = "v8w9x0y1z2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVIEW_STATUS_CHECK = "review_status IN ('pending_review', 'approved')"


def upgrade() -> None:
    """Add governance fields, backfill legacy rows, then enforce constraints."""
    op.add_column(
        "canonical_relationships", sa.Column("business_name", sa.String(200), nullable=True, server_default="")
    )
    op.add_column("canonical_relationships", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "canonical_relationships",
        sa.Column("review_status", sa.String(20), nullable=True, server_default="pending_review"),
    )
    op.add_column("canonical_relationships", sa.Column("ai_business_name", sa.String(200), nullable=True))
    op.add_column("canonical_relationships", sa.Column("ai_description", sa.Text(), nullable=True))
    op.add_column("canonical_relationships", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("canonical_relationships", sa.Column("reviewed_by", sa.Integer(), nullable=True))
    op.add_column("canonical_relationships", sa.Column("updated_by", sa.Integer(), nullable=True))

    _backfill_relationships()

    with op.batch_alter_table("canonical_relationships") as batch:
        batch.alter_column("business_name", existing_type=sa.String(200), nullable=False, server_default="")
        batch.alter_column(
            "review_status", existing_type=sa.String(20), nullable=False, server_default="pending_review"
        )
        batch.create_foreign_key(
            "fk_canonical_relationships_reviewed_by", "users", ["reviewed_by"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_canonical_relationships_updated_by", "users", ["updated_by"], ["id"], ondelete="SET NULL"
        )
        batch.create_check_constraint("ck_canonical_relationships_review_status", _REVIEW_STATUS_CHECK)
        batch.create_index("idx_canonical_relationships_review", ["connection_id", "review_status"])


def downgrade() -> None:
    """Drop governance fields and their constraints from canonical_relationships."""
    with op.batch_alter_table("canonical_relationships") as batch:
        batch.drop_constraint("ck_canonical_relationships_review_status", type_="check")
        batch.drop_constraint("fk_canonical_relationships_updated_by", type_="foreignkey")
        batch.drop_constraint("fk_canonical_relationships_reviewed_by", type_="foreignkey")
        batch.drop_index("idx_canonical_relationships_review")

    for column in (
        "updated_by",
        "reviewed_by",
        "reviewed_at",
        "ai_description",
        "ai_business_name",
        "review_status",
        "description",
        "business_name",
    ):
        op.drop_column("canonical_relationships", column)


def _backfill_relationships() -> None:
    """Label every existing relationship and set governance status from validity.

    Legacy rows have no human-approved business name, so we derive a deterministic
    label from the joined source/target table names (and the FK constraint name when
    available). A row is auto-approved only when its technical ``validation_status``
    is ``valid``; anything invalid or unknown stays ``pending_review`` for a human.
    """
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE canonical_relationships
            SET business_name = COALESCE(
                    (SELECT st_from.table_name || ' -> ' || st_to.table_name
                     FROM semantic_tables AS st_from, semantic_tables AS st_to
                     WHERE st_from.id = canonical_relationships.from_entity_id
                       AND st_to.id = canonical_relationships.to_entity_id),
                    'unknown -> unknown'
                )
                || CASE
                    WHEN canonical_relationships.constraint_name IS NOT NULL
                         AND canonical_relationships.constraint_name <> ''
                    THEN ' (' || canonical_relationships.constraint_name || ')'
                    ELSE ''
                END,
                review_status = CASE
                    WHEN canonical_relationships.validation_status = 'valid' THEN 'approved'
                    ELSE 'pending_review'
                END,
                ai_business_name = NULL,
                ai_description = NULL,
                description = NULL
            WHERE canonical_relationships.business_name IS NULL
               OR canonical_relationships.business_name = ''
            """
        )
    )
