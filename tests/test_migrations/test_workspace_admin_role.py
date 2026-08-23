"""Tests for the workspace admin role migration and backfill logic.

These tests verify the Alembic migration that:
1. Updates CHECK constraints to allow 'admin' role
2. Backfills one admin per workspace
3. Supports downgrade by converting admin → data_lead
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


def _create_old_schema_tables(engine: sa.engine.Engine) -> None:
    """Create tables with the OLD schema (before the admin-role migration).

    This simulates the state at revision l7m8n9o0p1q2 where CHECK constraints
    only allow 'data_lead' and 'member'.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) NOT NULL UNIQUE,
                username VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(200) NOT NULL DEFAULT '',
                role VARCHAR(50) NOT NULL DEFAULT 'analyst',
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(200) NOT NULL,
                slug VARCHAR(120) NOT NULL UNIQUE,
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS organization_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL DEFAULT 'member',
                joined_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_organization_members_org_user UNIQUE(org_id, user_id),
                CONSTRAINT ck_organization_members_role CHECK(role IN ('data_lead', 'member'))
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS organization_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                inviter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                invitee_email VARCHAR(255),
                role VARCHAR(20) NOT NULL DEFAULT 'member',
                token_hash VARCHAR(64) NOT NULL,
                expires_at DATETIME NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                accepted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                accepted_at DATETIME,
                revoked_at DATETIME,
                created_at DATETIME NOT NULL,
                CONSTRAINT uq_organization_invitations_token_hash UNIQUE(token_hash),
                CONSTRAINT ck_organization_invitations_role CHECK(role IN ('data_lead', 'member'))
            )
        """)
        )
        conn.execute(text("CREATE INDEX idx_organization_members_org_role ON organization_members (org_id, role)"))
        conn.execute(text("CREATE INDEX idx_organization_members_user_org ON organization_members (user_id, org_id)"))
        conn.execute(
            text("CREATE INDEX idx_organization_invitations_org_status ON organization_invitations (org_id, status)")
        )


def _seed_workspaces(bind: sa.engine.Connection, now: datetime) -> None:
    """Insert three workspaces exercising every backfill branch.

    Workspace 1 — creator is an active member (role=data_lead) → becomes admin.
    Workspace 2 — creator is NOT a member; earliest Data Lead by (created_at, id) → becomes admin.
    Workspace 3 — creator is NOT a member; no Data Lead; earliest member by (created_at, id) → becomes admin.
    """
    for uid in range(1, 7):
        bind.execute(
            text(
                "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                "VALUES (:id, :email, :username, 'hash', :name, 'analyst', 'active', :now, :now)"
            ),
            {"id": uid, "email": f"u{uid}@t.co", "username": f"u{uid}", "name": f"User {uid}", "now": now},
        )

    for oid, creator in [(1, 1), (2, 2), (3, 3)]:
        bind.execute(
            text(
                "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                "VALUES (:id, :name, :slug, :creator, :now, :now)"
            ),
            {"id": oid, "name": f"Org {oid}", "slug": f"org-{oid}", "creator": creator, "now": now},
        )

    # Workspace 1: creator (user 1) is an active data_lead member
    bind.execute(
        text(
            "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
            "VALUES (1, 1, 'data_lead', :now, :now)"
        ),
        {"now": now},
    )

    # Workspace 2: creator (user 2) is NOT a member.
    # Two data_leads: user 4 joined later, user 3 joined earlier.
    bind.execute(
        text(
            "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
            "VALUES (2, 4, 'data_lead', :later, :later)"
        ),
        {"later": datetime(2025, 1, 2, tzinfo=UTC)},
    )
    bind.execute(
        text(
            "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
            "VALUES (2, 3, 'data_lead', :earlier, :earlier)"
        ),
        {"earlier": datetime(2025, 1, 1, tzinfo=UTC)},
    )

    # Workspace 3: creator (user 3) is NOT a member; no data_lead; two plain members.
    bind.execute(
        text(
            "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
            "VALUES (3, 5, 'member', :later, :later)"
        ),
        {"later": datetime(2025, 2, 2, tzinfo=UTC)},
    )
    bind.execute(
        text(
            "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
            "VALUES (3, 6, 'member', :earlier, :earlier)"
        ),
        {"earlier": datetime(2025, 2, 1, tzinfo=UTC)},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine(tmp_path):
    """Yield a synchronous SQLite engine with the old schema pre-applied."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    _create_old_schema_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_db(db_engine):
    """Yield a synchronous SQLite engine with old schema + seeded workspaces."""
    now = datetime.now(UTC)
    with db_engine.begin() as conn:
        _seed_workspaces(conn, now)
    return db_engine


def _import_migration_module():
    """Import the actual migration module from alembic/versions/."""
    import importlib.util
    import sys
    from pathlib import Path

    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*_add_workspace_admin_role.py"))
    if not migration_files:
        pytest.fail(
            "Migration file '*_add_workspace_admin_role.py' not found in alembic/versions/. Create the migration first."
        )

    migration_path = migration_files[0]
    spec = importlib.util.spec_from_file_location("_workspace_admin_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_workspace_admin_migration"] = module
    spec.loader.exec_module(module)
    return module


def _run_upgrade(engine: sa.engine.Engine) -> None:
    """Run the migration's upgrade() against the given engine."""
    module = _import_migration_module()

    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with patch.object(module, "op", operations):
            module.upgrade()
        conn.commit()


def _run_downgrade(engine: sa.engine.Engine) -> None:
    """Run the migration's downgrade() against the given engine."""
    module = _import_migration_module()

    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with patch.object(module, "op", operations):
            module.downgrade()
        conn.commit()


# ---------------------------------------------------------------------------
# Tests — Pre-migration constraints
# ---------------------------------------------------------------------------


class TestPreMigrationConstraints:
    """Before the new migration, 'admin' must be rejected by CHECK constraints."""

    def test_admin_rejected_in_members(self, db_engine):
        now = datetime.now(UTC)
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                    "VALUES (1, 'a@b.co', 'u1', 'hash', 'U', 'analyst', 'active', :now, :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                    "VALUES (1, 'O', 'o', 1, :now, :now)"
                ),
                {"now": now},
            )
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                        "VALUES (1, 1, 'admin', :now, :now)"
                    ),
                    {"now": now},
                )

    def test_admin_rejected_in_invitations(self, db_engine):
        now = datetime.now(UTC)
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                    "VALUES (1, 'a@b.co', 'u1', 'hash', 'U', 'analyst', 'active', :now, :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                    "VALUES (1, 'O', 'o', 1, :now, :now)"
                ),
                {"now": now},
            )
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO organization_invitations "
                        "(org_id, inviter_id, invitee_email, role, token_hash, expires_at, status, created_at) "
                        "VALUES (1, 1, 'x@y.co', 'admin', 'tok', :now, 'pending', :now)"
                    ),
                    {"now": now},
                )


# ---------------------------------------------------------------------------
# Tests — Backfill logic
# ---------------------------------------------------------------------------


class TestBackfillLogic:
    """After the migration, exactly one admin per workspace is backfilled."""

    def test_creator_member_becomes_admin(self, seeded_db):
        """Workspace 1: creator is an active data_lead → promoted to admin."""
        _run_upgrade(seeded_db)
        with seeded_db.connect() as conn:
            admins = (
                conn.execute(text("SELECT user_id FROM organization_members WHERE org_id = 1 AND role = 'admin'"))
                .scalars()
                .all()
            )
            assert admins == [1], f"Expected user 1 as admin of org 1, got {admins}"

    def test_earliest_data_lead_fallback(self, seeded_db):
        """Workspace 2: creator absent; earliest Data Lead (user 3) → admin."""
        _run_upgrade(seeded_db)
        with seeded_db.connect() as conn:
            admins = (
                conn.execute(text("SELECT user_id FROM organization_members WHERE org_id = 2 AND role = 'admin'"))
                .scalars()
                .all()
            )
            assert admins == [3], f"Expected user 3 as admin of org 2, got {admins}"

    def test_oldest_member_fallback(self, seeded_db):
        """Workspace 3: no Data Lead; earliest member (user 6) → admin."""
        _run_upgrade(seeded_db)
        with seeded_db.connect() as conn:
            admins = (
                conn.execute(text("SELECT user_id FROM organization_members WHERE org_id = 3 AND role = 'admin'"))
                .scalars()
                .all()
            )
            assert admins == [6], f"Expected user 6 as admin of org 3, got {admins}"

    def test_exactly_one_admin_per_workspace(self, seeded_db):
        """Each workspace must have exactly one admin after backfill."""
        _run_upgrade(seeded_db)
        with seeded_db.connect() as conn:
            counts = conn.execute(
                text(
                    "SELECT org_id, COUNT(*) AS cnt FROM organization_members "
                    "WHERE role = 'admin' GROUP BY org_id ORDER BY org_id"
                )
            ).fetchall()
            assert [(r[0], r[1]) for r in counts] == [(1, 1), (2, 1), (3, 1)]

    def test_non_promoted_data_leads_unchanged(self, seeded_db):
        """Data Leads who were NOT promoted keep their original role."""
        _run_upgrade(seeded_db)
        with seeded_db.connect() as conn:
            role = conn.execute(
                text("SELECT role FROM organization_members WHERE org_id = 2 AND user_id = 4")
            ).scalar_one()
            assert role == "data_lead"


# ---------------------------------------------------------------------------
# Tests — Post-migration constraints
# ---------------------------------------------------------------------------


class TestPostMigrationConstraints:
    """After the migration, 'admin' must be accepted by CHECK constraints."""

    def test_admin_accepted_in_members(self, db_engine):
        now = datetime.now(UTC)
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                    "VALUES (1, 'a@b.co', 'u1', 'hash', 'U', 'analyst', 'active', :now, :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                    "VALUES (1, 'O', 'o', 1, :now, :now)"
                ),
                {"now": now},
            )
        _run_upgrade(db_engine)
        with db_engine.begin() as conn:
            # Should NOT raise
            conn.execute(
                text(
                    "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                    "VALUES (1, 1, 'admin', :now, :now)"
                ),
                {"now": now},
            )

    def test_admin_accepted_in_invitations(self, db_engine):
        now = datetime.now(UTC)
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                    "VALUES (1, 'a@b.co', 'u1', 'hash', 'U', 'analyst', 'active', :now, :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                    "VALUES (1, 'O', 'o', 1, :now, :now)"
                ),
                {"now": now},
            )
        _run_upgrade(db_engine)
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO organization_invitations "
                    "(org_id, inviter_id, invitee_email, role, token_hash, expires_at, status, created_at) "
                    "VALUES (1, 1, 'x@y.co', 'admin', 'tok', :now, 'pending', :now)"
                ),
                {"now": now},
            )

    def test_upgrade_preserves_preceding_migration_indexes(self, seeded_db):
        """Batch constraint replacement must retain all explicit RBAC indexes."""
        expected = {
            "organization_members": {
                "idx_organization_members_org_role",
                "idx_organization_members_user_org",
            },
            "organization_invitations": {"idx_organization_invitations_org_status"},
        }

        _run_upgrade(seeded_db)

        inspector = sa.inspect(seeded_db)
        for table, names in expected.items():
            assert {index["name"] for index in inspector.get_indexes(table)} >= names


# ---------------------------------------------------------------------------
# Tests — Downgrade
# ---------------------------------------------------------------------------


class TestDowngrade:
    """Downgrade converts admin → data_lead and restores old constraints."""

    def test_downgrade_converts_admin_to_data_lead(self, seeded_db):
        _run_upgrade(seeded_db)
        with seeded_db.connect() as conn:
            admin_count = conn.execute(
                text("SELECT COUNT(*) FROM organization_members WHERE role = 'admin'")
            ).scalar_one()
            assert admin_count == 3
        _run_downgrade(seeded_db)
        with seeded_db.connect() as conn:
            admin_count = conn.execute(
                text("SELECT COUNT(*) FROM organization_members WHERE role = 'admin'")
            ).scalar_one()
            assert admin_count == 0, "admin rows should be converted to data_lead on downgrade"
            dl_count = conn.execute(
                text("SELECT COUNT(*) FROM organization_members WHERE role = 'data_lead'")
            ).scalar_one()
            assert dl_count >= 3, "former admins should be data_lead after downgrade"

    def test_downgrade_restores_constraint(self, seeded_db):
        _run_upgrade(seeded_db)
        _run_downgrade(seeded_db)
        now = datetime.now(UTC)
        with seeded_db.begin() as conn:
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                        "VALUES (1, 1, 'admin', :now, :now)"
                    ),
                    {"now": now},
                )

    def test_upgrade_downgrade_upgrade_cycle_preserves_indexes(self, seeded_db):
        """A realistic reversal remains repeatable without losing schema indexes."""
        _run_upgrade(seeded_db)
        _run_downgrade(seeded_db)
        _run_upgrade(seeded_db)

        inspector = sa.inspect(seeded_db)
        assert {item["name"] for item in inspector.get_indexes("organization_members")} >= {
            "idx_organization_members_org_role",
            "idx_organization_members_user_org",
        }
        assert {item["name"] for item in inspector.get_indexes("organization_invitations")} >= {
            "idx_organization_invitations_org_status"
        }


# ---------------------------------------------------------------------------
# Tests — created_by=NULL fallback and zero-member workspace
# ---------------------------------------------------------------------------


class TestNullCreatorFallback:
    """Workspaces with created_by=NULL fall back deterministically to earliest Data Lead."""

    def test_null_creator_falls_back_to_earliest_data_lead(self, db_engine):
        """When created_by is NULL, the earliest Data Lead by (joined_at, id) becomes admin."""
        now = datetime.now(UTC)
        with db_engine.begin() as conn:
            # Seed users
            for uid in range(1, 4):
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                        "VALUES (:id, :email, :username, 'hash', :name, 'analyst', 'active', :now, :now)"
                    ),
                    {"id": uid, "email": f"u{uid}@t.co", "username": f"u{uid}", "name": f"User {uid}", "now": now},
                )
            # Workspace with created_by=NULL
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                    "VALUES (1, 'Null Creator Org', 'null-creator', NULL, :now, :now)"
                ),
                {"now": now},
            )
            # Two data_leads: user 2 joined later, user 1 joined earlier
            conn.execute(
                text(
                    "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                    "VALUES (1, 2, 'data_lead', :later, :later)"
                ),
                {"later": datetime(2025, 3, 2, tzinfo=UTC)},
            )
            conn.execute(
                text(
                    "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                    "VALUES (1, 1, 'data_lead', :earlier, :earlier)"
                ),
                {"earlier": datetime(2025, 3, 1, tzinfo=UTC)},
            )

        _run_upgrade(db_engine)
        with db_engine.connect() as conn:
            admins = (
                conn.execute(text("SELECT user_id FROM organization_members WHERE org_id = 1 AND role = 'admin'"))
                .scalars()
                .all()
            )
            assert admins == [1], f"Expected user 1 (earliest DL) as admin, got {admins}"

    def test_null_creator_no_data_lead_falls_back_to_earliest_member(self, db_engine):
        """When created_by is NULL and no Data Lead exists, earliest member becomes admin."""
        now = datetime.now(UTC)
        with db_engine.begin() as conn:
            for uid in range(1, 4):
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                        "VALUES (:id, :email, :username, 'hash', :name, 'analyst', 'active', :now, :now)"
                    ),
                    {"id": uid, "email": f"u{uid}@t.co", "username": f"u{uid}", "name": f"User {uid}", "now": now},
                )
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                    "VALUES (1, 'Null Creator Org', 'null-creator', NULL, :now, :now)"
                ),
                {"now": now},
            )
            # Only plain members, no data_lead
            conn.execute(
                text(
                    "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                    "VALUES (1, 2, 'member', :later, :later)"
                ),
                {"later": datetime(2025, 3, 2, tzinfo=UTC)},
            )
            conn.execute(
                text(
                    "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                    "VALUES (1, 1, 'member', :earlier, :earlier)"
                ),
                {"earlier": datetime(2025, 3, 1, tzinfo=UTC)},
            )

        _run_upgrade(db_engine)
        with db_engine.connect() as conn:
            admins = (
                conn.execute(text("SELECT user_id FROM organization_members WHERE org_id = 1 AND role = 'admin'"))
                .scalars()
                .all()
            )
            assert admins == [1], f"Expected user 1 (earliest member) as admin, got {admins}"

    def test_zero_member_workspace_no_admin_assigned(self, db_engine):
        """A workspace with no members gets no admin — the migration skips it without error.

        This is expected behavior: the backfill loop iterates over workspaces and
        attempts each priority tier. When all three tiers find no candidate the
        workspace is simply left without an admin. A future admin must be assigned
        manually or through a separate process.
        """
        now = datetime.now(UTC)
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, username, hashed_password, full_name, role, status, created_at, updated_at) "
                    "VALUES (1, 'u1@t.co', 'u1', 'hash', 'User 1', 'analyst', 'active', :now, :now)"
                ),
                {"now": now},
            )
            # Workspace with created_by=NULL and zero members
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, created_by, created_at, updated_at) "
                    "VALUES (1, 'Empty Org', 'empty', NULL, :now, :now)"
                ),
                {"now": now},
            )

        # Migration should complete without error
        _run_upgrade(db_engine)
        with db_engine.connect() as conn:
            admin_count = conn.execute(
                text("SELECT COUNT(*) FROM organization_members WHERE org_id = 1 AND role = 'admin'")
            ).scalar_one()
            assert admin_count == 0, "Zero-member workspace should have no admin assigned"
