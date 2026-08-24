"""Add HITL schema review state and append-only metric version metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2q3r4s5t6u7"
down_revision: str | Sequence[str] | None = "o1p2q3r4s5t6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVIEW_TABLES = ("semantic_tables", "semantic_columns")
_REVIEW_CHECK = "review_status IN ('pending_review', 'approved')"
_VERSION_STATUS_CHECK = "status IN ('pending_approval', 'needs_review', 'approved', 'superseded', 'rejected')"


def _review_columns() -> list[sa.Column]:
    """Build the review-state columns shared by tables and columns metadata."""
    return [
        sa.Column("review_status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("ai_business_name", sa.String(200), nullable=True),
        sa.Column("ai_description", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    ]


def _add_review_state() -> None:
    """Add review columns, FKs, index, and CHECK constraint to one metadata table."""
    for table in _REVIEW_TABLES:
        for column in _review_columns():
            op.add_column(table, column)
        parent = "db_id" if table == "semantic_tables" else "table_id"
        op.create_index(f"idx_{table}_{parent[:-3]}_review", table, [parent, "review_status"])
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(
                f"fk_{table}_reviewed_by", "users", ["reviewed_by"], ["id"], ondelete="SET NULL"
            )
            batch.create_foreign_key(f"fk_{table}_updated_by", "users", ["updated_by"], ["id"], ondelete="SET NULL")
            batch.create_check_constraint(f"ck_{table}_review_status", _REVIEW_CHECK)


def _backfill_reviewed_stamp() -> None:
    """Treat every pre-existing row as already approved by its creator."""
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE semantic_tables SET reviewed_by = created_by, reviewed_at = created_at "
            "WHERE review_status = 'approved'"
        )
    )
    bind.execute(sa.text("UPDATE semantic_columns SET reviewed_at = created_at WHERE review_status = 'approved'"))


def _dedupe_metric_versions() -> None:
    """Keep only the newest row per (metric_id, version) before enforcing uniqueness."""
    op.get_bind().execute(
        sa.text(
            """
            DELETE FROM metric_versions
            WHERE id NOT IN (
                SELECT MAX(id) FROM metric_versions GROUP BY metric_id, version
            )
            """
        )
    )


def _add_version_columns() -> None:
    """Extend metric_versions with lifecycle, lineage, and approval columns."""
    op.add_column("metric_versions", sa.Column("name", sa.String(200), nullable=False, server_default=""))
    op.add_column("metric_versions", sa.Column("status", sa.String(20), nullable=False, server_default="superseded"))
    op.add_column("metric_versions", sa.Column("parent_version", sa.Integer(), nullable=True))
    op.add_column("metric_versions", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column("metric_versions", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("metric_versions") as batch:
        batch.create_foreign_key(
            "fk_metric_versions_approved_by", "users", ["approved_by"], ["id"], ondelete="SET NULL"
        )
        batch.create_unique_constraint("uq_metric_versions_metric_version", ["metric_id", "version"])


def _backfill_version_metadata() -> None:
    """Mirror the live metric row onto its matching historical snapshot."""
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE metric_versions
            SET name = COALESCE((
                    SELECT sm.name FROM semantic_metrics AS sm WHERE sm.id = metric_versions.metric_id
                ), ''),
                parent_version = CASE WHEN version > 1 THEN version - 1 ELSE NULL END
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE metric_versions
            SET status = COALESCE((
                    SELECT CASE sm.status
                        WHEN 'approved' THEN 'approved'
                        WHEN 'needs_review' THEN 'needs_review'
                        ELSE 'pending_approval'
                    END
                    FROM semantic_metrics AS sm
                    WHERE sm.id = metric_versions.metric_id
                ), 'superseded'),
                approved_by = (
                    SELECT sm.approved_by FROM semantic_metrics AS sm WHERE sm.id = metric_versions.metric_id
                )
            WHERE EXISTS (
                SELECT 1 FROM semantic_metrics AS sm
                WHERE sm.id = metric_versions.metric_id AND sm.version = metric_versions.version
            )
            """
        )
    )
    bind.execute(
        sa.text("UPDATE metric_versions SET approved_at = created_at WHERE status = 'approved' AND approved_at IS NULL")
    )


def _add_version_status_constraint() -> None:
    """Enforce the metric version lifecycle only after legacy rows are normalized."""
    with op.batch_alter_table("metric_versions") as batch:
        batch.create_check_constraint("ck_metric_versions_status", _VERSION_STATUS_CHECK)


def upgrade() -> None:
    """Add schema review state and append-only metric version metadata."""
    _add_review_state()
    _backfill_reviewed_stamp()
    _dedupe_metric_versions()
    _add_version_columns()
    _backfill_version_metadata()
    _add_version_status_constraint()


def downgrade() -> None:
    """Drop schema review state and metric version lifecycle metadata."""
    with op.batch_alter_table("metric_versions") as batch:
        batch.drop_constraint("ck_metric_versions_status", type_="check")
        batch.drop_constraint("uq_metric_versions_metric_version", type_="unique")
        batch.drop_constraint("fk_metric_versions_approved_by", type_="foreignkey")
    for column in ("approved_at", "approved_by", "parent_version", "status", "name"):
        op.drop_column("metric_versions", column)

    for table in _REVIEW_TABLES:
        parent = "db_id" if table == "semantic_tables" else "table_id"
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"ck_{table}_review_status", type_="check")
            batch.drop_constraint(f"fk_{table}_updated_by", type_="foreignkey")
            batch.drop_constraint(f"fk_{table}_reviewed_by", type_="foreignkey")
        op.drop_index(f"idx_{table}_{parent[:-3]}_review", table_name=table)
        for column in (
            "updated_by",
            "reviewed_at",
            "reviewed_by",
            "ai_description",
            "ai_business_name",
            "review_status",
        ):
            op.drop_column(table, column)
