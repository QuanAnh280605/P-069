"""Constrain metric status to valid lifecycle values."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m8n9o0p1q2r3"
down_revision: str | Sequence[str] | None = "l7m8n9o0p1q2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VALID_STATUSES: tuple[str, ...] = (
    "draft",
    "pending_approval",
    "approved",
    "needs_review",
    "unverified",
)
_CONSTRAINT_NAME = "ck_semantic_metrics_status"


def _valid_status_in_clause() -> str:
    """Render the quoted IN-list shared by the sanitizer and the CHECK constraint."""
    return "(" + ", ".join(f"'{value}'" for value in VALID_STATUSES) + ")"


def _has_constraint(table: str, name: str) -> bool:
    """Check if a CHECK constraint already exists."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite doesn't expose CHECK constraints via inspector easily
        return False
    return any(item["name"] == name for item in sa.inspect(bind).get_check_constraints(table))


def _add_status_constraint() -> None:
    """Add a portable status constraint for SQLite and PostgreSQL."""
    if _has_constraint("semantic_metrics", _CONSTRAINT_NAME):
        return
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("semantic_metrics", recreate="always") as batch:
            batch.create_check_constraint(
                _CONSTRAINT_NAME,
                f"status IN {_valid_status_in_clause()}",
            )
        return
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "semantic_metrics",
        f"status IN {_valid_status_in_clause()}",
    )


def _sanitize_legacy_statuses() -> None:
    """Map NULL or unrecognized metric statuses to needs_review."""
    bind = op.get_bind()
    statement = sa.text(
        "UPDATE semantic_metrics SET status = 'needs_review' WHERE status IS NULL OR status NOT IN :valid"
    )
    statement = statement.bindparams(sa.bindparam("valid", expanding=True))
    bind.execute(statement, {"valid": list(VALID_STATUSES)})


def _remap_member_pending_to_unverified() -> None:
    """Flag member-created pending metrics on Workspace databases as unverified."""
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE semantic_metrics
            SET status = 'unverified'
            WHERE status = 'pending_approval'
              AND EXISTS (
                  SELECT 1
                  FROM semantic_databases AS sd
                  JOIN organization_members AS om
                    ON om.org_id = sd.org_id AND om.user_id = semantic_metrics.created_by
                  WHERE sd.id = semantic_metrics.db_id AND om.role = 'member'
              )
            """
        )
    )


def _drop_status_constraint() -> None:
    """Drop a portable status constraint for SQLite and PostgreSQL."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("semantic_metrics", recreate="always") as batch:
            batch.drop_constraint(_CONSTRAINT_NAME, type_="check")
        return
    op.drop_constraint(_CONSTRAINT_NAME, "semantic_metrics", type_="check")


def upgrade() -> None:
    """Sanitize legacy statuses, remap member drafts, then enforce the CHECK constraint."""
    _sanitize_legacy_statuses()
    _remap_member_pending_to_unverified()
    _add_status_constraint()


def downgrade() -> None:
    """Convert unverified to pending_approval and remove constraint."""
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE semantic_metrics SET status = 'pending_approval' WHERE status = 'unverified'"))
    _drop_status_constraint()
