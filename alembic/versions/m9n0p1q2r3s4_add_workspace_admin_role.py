"""Add workspace admin role with legacy backfill."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m9n0p1q2r3s4"
down_revision: str | Sequence[str] | None = "l7m8n9o0p1q2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _update_role_constraint(
    bind: sa.engine.Connection,
    table: str,
    constraint_name: str,
    new_expr: str,
) -> None:
    """Replace a role constraint while preserving reflected indexes."""
    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table(table, recreate=recreate) as batch:
        batch.drop_constraint(constraint_name, type_="check")
        batch.create_check_constraint(constraint_name, new_expr)


def _backfill_admins(bind: sa.engine.Connection) -> None:
    """Backfill exactly one admin per workspace in deterministic order."""
    orgs = bind.execute(sa.text("SELECT id, created_by FROM organizations ORDER BY id")).mappings().all()

    for org in orgs:
        org_id = org["id"]
        created_by = org["created_by"]

        # Priority 1: workspace creator if they are an active member
        if created_by is not None:
            creator_member = bind.execute(
                sa.text("SELECT id FROM organization_members WHERE org_id = :org_id AND user_id = :created_by"),
                {"org_id": org_id, "created_by": created_by},
            ).scalar_one_or_none()

            if creator_member is not None:
                bind.execute(
                    sa.text(
                        "UPDATE organization_members SET role = 'admin' "
                        "WHERE org_id = :org_id AND user_id = :created_by"
                    ),
                    {"org_id": org_id, "created_by": created_by},
                )
                continue

        # Priority 2: earliest Data Lead by (joined_at, id)
        earliest_dl = bind.execute(
            sa.text(
                "SELECT id FROM organization_members "
                "WHERE org_id = :org_id AND role = 'data_lead' "
                "ORDER BY joined_at ASC, id ASC LIMIT 1"
            ),
            {"org_id": org_id},
        ).scalar_one_or_none()

        if earliest_dl is not None:
            bind.execute(
                sa.text("UPDATE organization_members SET role = 'admin' WHERE id = :id"),
                {"id": earliest_dl},
            )
            continue

        # Priority 3: earliest member by (joined_at, id)
        earliest_member = bind.execute(
            sa.text(
                "SELECT id FROM organization_members "
                "WHERE org_id = :org_id AND role = 'member' "
                "ORDER BY joined_at ASC, id ASC LIMIT 1"
            ),
            {"org_id": org_id},
        ).scalar_one_or_none()

        if earliest_member is not None:
            bind.execute(
                sa.text("UPDATE organization_members SET role = 'admin' WHERE id = :id"),
                {"id": earliest_member},
            )


def upgrade() -> None:
    """Add admin role to CHECK constraints and backfill one admin per workspace."""
    bind = op.get_bind()

    # Step 1: Update CHECK constraints to allow 'admin'
    _update_role_constraint(
        bind,
        "organization_members",
        "ck_organization_members_role",
        "role IN ('admin', 'data_lead', 'member')",
    )
    _update_role_constraint(
        bind,
        "organization_invitations",
        "ck_organization_invitations_role",
        "role IN ('admin', 'data_lead', 'member')",
    )

    # Step 2: Backfill exactly one admin per workspace
    _backfill_admins(bind)


def downgrade() -> None:
    """Convert admin rows to data_lead and restore old constraints."""
    bind = op.get_bind()

    # Step 1: Convert all admin roles to data_lead
    bind.execute(sa.text("UPDATE organization_members SET role = 'data_lead' WHERE role = 'admin'"))
    bind.execute(sa.text("UPDATE organization_invitations SET role = 'data_lead' WHERE role = 'admin'"))

    # Step 2: Restore old CHECK constraints (no admin)
    _update_role_constraint(
        bind,
        "organization_members",
        "ck_organization_members_role",
        "role IN ('data_lead', 'member')",
    )
    _update_role_constraint(
        bind,
        "organization_invitations",
        "ck_organization_invitations_role",
        "role IN ('data_lead', 'member')",
    )
