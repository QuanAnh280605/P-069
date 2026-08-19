"""add organization workspaces, memberships, invitations, and resource scope"""

from collections.abc import Sequence
from datetime import UTC, datetime
import re

import sqlalchemy as sa

from alembic import op

revision: str = "j5k6l7m8n9o0"
down_revision: str | Sequence[str] | None = "i4j5k6l7m8n9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _slug(value: str) -> str:
    """Create a stable migration-safe slug."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "workspace"


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    """Create Workspace tables and backfill existing semantic databases safely."""
    _create_organization_tables()
    if not _column_exists("semantic_databases", "org_id"):
        op.add_column("semantic_databases", sa.Column("org_id", sa.Integer(), nullable=True))
    _backfill_organizations()
    _add_semantic_database_fk_and_index()


def _create_organization_tables() -> None:
    if not _table_exists("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(120), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        )
    if not _table_exists("organization_members"):
        op.create_table(
            "organization_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(20), nullable=False, server_default="member"),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("org_id", "user_id", name="uq_organization_members_org_user"),
        )
        op.create_index("idx_organization_members_org_role", "organization_members", ["org_id", "role"])
        op.create_index("idx_organization_members_user_org", "organization_members", ["user_id", "org_id"])
    if not _table_exists("organization_invitations"):
        op.create_table(
            "organization_invitations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("inviter_id", sa.Integer(), nullable=True),
            sa.Column("invitee_email", sa.String(255), nullable=True),
            sa.Column("role", sa.String(20), nullable=False, server_default="member"),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("accepted_by", sa.Integer(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["accepted_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("token_hash", name="uq_organization_invitations_token_hash"),
        )
        op.create_index("idx_organization_invitations_org_status", "organization_invitations", ["org_id", "status"])
    if not _table_exists("organization_audit_logs"):
        op.create_table(
            "organization_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("target_user_id", sa.Integer(), nullable=True),
            sa.Column("target_invitation_id", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_invitation_id"], ["organization_invitations.id"], ondelete="SET NULL"),
        )
        op.create_index("idx_organization_audit_logs_org_created", "organization_audit_logs", ["org_id", "created_at"])


def _backfill_organizations() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    users = bind.execute(sa.text("SELECT id, username, full_name FROM users ORDER BY id")).mappings().all()
    semantic_rows = bind.execute(sa.text("SELECT id, created_by FROM semantic_databases ORDER BY id")).mappings().all()
    org_by_user: dict[int, int] = {}

    for user in users:
        has_resource = any(row["created_by"] == user["id"] for row in semantic_rows)
        if not has_resource:
            continue
        org_by_user[user["id"]] = _get_or_create_org(
            bind, f"{user['full_name'] or user['username']}'s Workspace", f"legacy-user-{user['id']}", user["id"], now
        )
        _ensure_membership(bind, org_by_user[user["id"]], user["id"], "admin", now)

    fallback_owner = users[0]["id"] if users else None
    fallback_org = _get_or_create_org(bind, "Default Workspace", "default-workspace", fallback_owner, now)
    if fallback_owner is not None:
        _ensure_membership(bind, fallback_org, fallback_owner, "admin", now)

    for user in users:
        if user["id"] not in org_by_user:
            _ensure_membership(bind, fallback_org, user["id"], "member", now)
    for row in semantic_rows:
        org_id = org_by_user.get(row["created_by"], fallback_org)
        bind.execute(sa.text("UPDATE semantic_databases SET org_id = :org_id WHERE id = :id"), {"org_id": org_id, "id": row["id"]})


def _get_or_create_org(bind, name: str, slug: str, owner_id: int | None, now: datetime) -> int:
    existing = bind.execute(sa.text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": slug}).scalar_one_or_none()
    if existing is not None:
        return int(existing)
    bind.execute(
        sa.text("INSERT INTO organizations (name, slug, created_by, created_at, updated_at) VALUES (:name, :slug, :owner, :created_at, :updated_at)"),
        {"name": name[:200], "slug": _slug(slug)[:120], "owner": owner_id, "created_at": now, "updated_at": now},
    )
    created = bind.execute(sa.text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": slug}).scalar_one()
    return int(created)


def _ensure_membership(bind, org_id: int, user_id: int, role: str, now: datetime) -> None:
    exists = bind.execute(
        sa.text("SELECT id FROM organization_members WHERE org_id = :org_id AND user_id = :user_id"),
        {"org_id": org_id, "user_id": user_id},
    ).scalar_one_or_none()
    if exists is None:
        bind.execute(
            sa.text("INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) VALUES (:org_id, :user_id, :role, :joined_at, :updated_at)"),
            {"org_id": org_id, "user_id": user_id, "role": role, "joined_at": now, "updated_at": now},
        )


def _add_semantic_database_fk_and_index() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_keys = {item["name"] for item in inspector.get_foreign_keys("semantic_databases")}
    if "fk_semantic_databases_org" not in foreign_keys:
        with op.batch_alter_table("semantic_databases", recreate="auto") as batch_op:
            batch_op.create_foreign_key(
                "fk_semantic_databases_org",
                "organizations",
                ["org_id"],
                ["id"],
                ondelete="CASCADE",
            )
    if "idx_semantic_databases_org" not in {index["name"] for index in inspector.get_indexes("semantic_databases")}:
        op.create_index("idx_semantic_databases_org", "semantic_databases", ["org_id"])


def downgrade() -> None:
    """Remove Workspace schema while preserving existing semantic records."""
    op.drop_index("idx_semantic_databases_org", table_name="semantic_databases")
    op.drop_column("semantic_databases", "org_id")
    for table in ("organization_audit_logs", "organization_invitations", "organization_members", "organizations"):
        if _table_exists(table):
            op.drop_table(table)
