"""Retire the Workspace admin role in favor of data_lead."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "l7m8n9o0p1q2"
down_revision: str | Sequence[str] | None = "k6l7m8n9o0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_role_constraint(table: str, name: str) -> None:
    """Add a portable role constraint for SQLite and PostgreSQL."""
    if any(item["name"] == name for item in sa.inspect(op.get_bind()).get_check_constraints(table)):
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.create_check_constraint(name, "role IN ('data_lead', 'member')")
        return
    op.create_check_constraint(name, table, "role IN ('data_lead', 'member')")


def _drop_role_constraint(table: str, name: str) -> None:
    """Drop a portable role constraint for SQLite and PostgreSQL."""
    if not any(item["name"] == name for item in sa.inspect(op.get_bind()).get_check_constraints(table)):
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_constraint(name, type_="check")
        return
    op.drop_constraint(name, table, type_="check")


def _assert_valid_roles(table: str) -> None:
    """Fail clearly if legacy data contains an unsupported Workspace role."""
    invalid = op.get_bind().execute(
        sa.text(f"SELECT DISTINCT role FROM {table} WHERE role NOT IN ('data_lead', 'member')")
    ).scalars().all()
    if invalid:
        raise RuntimeError(f"Unsupported Workspace roles in {table}: {', '.join(sorted(invalid))}")


def upgrade() -> None:
    """Migrate Workspace admins and reject future legacy role values."""
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE organization_members SET role = 'data_lead' WHERE role = 'admin'")
    )
    bind.execute(
        sa.text("UPDATE organization_invitations SET role = 'data_lead' WHERE role = 'admin'")
    )
    _assert_valid_roles("organization_members")
    _assert_valid_roles("organization_invitations")
    _add_role_constraint(
        "organization_members", "ck_organization_members_role"
    )
    _add_role_constraint(
        "organization_invitations", "ck_organization_invitations_role"
    )


def downgrade() -> None:
    """Remove constraints; role data remains data_lead and needs backup restore to roll back."""
    _drop_role_constraint(
        "organization_invitations", "ck_organization_invitations_role"
    )
    _drop_role_constraint(
        "organization_members", "ck_organization_members_role"
    )
