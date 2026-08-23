"""Tests for the metric status CHECK constraint migration."""

from datetime import datetime
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


@pytest.fixture
def engine():
    """Create a fresh in-memory SQLite engine for migration testing."""
    eng = create_engine("sqlite:///:memory:")
    yield eng
    eng.dispose()


def _create_schema_with_constraint(engine) -> None:
    """Create schema with the CHECK constraint already applied."""
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE semantic_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id INTEGER NOT NULL,
                created_by INTEGER,
                name VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                sql_template TEXT NOT NULL,
                source VARCHAR(20) NOT NULL DEFAULT 'manual',
                status VARCHAR(20) NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'pending_approval', 'needs_review', 'approved', 'unverified')),
                base_entity_id INTEGER,
                formula TEXT NOT NULL DEFAULT '',
                aggregation_type VARCHAR(50),
                definition JSON,
                version INTEGER NOT NULL DEFAULT 1,
                approved_by INTEGER,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        )


def test_check_constraint_accepts_valid_statuses(engine) -> None:
    """CHECK constraint allows all valid status values."""
    _create_schema_with_constraint(engine)

    valid_statuses = ["draft", "pending_approval", "needs_review", "approved", "unverified"]
    with engine.begin() as conn:
        for status in valid_statuses:
            conn.execute(
                text("""
                INSERT INTO semantic_metrics (db_id, name, description, sql_template, status, created_at, updated_at)
                VALUES (1, :name, 'test', 'test', :status, datetime('now'), datetime('now'))
            """),
                {"status": status, "name": f"test_{status}"},
            )


def test_check_constraint_rejects_invalid_status(engine) -> None:
    """CHECK constraint rejects unknown status values."""
    _create_schema_with_constraint(engine)

    with pytest.raises(Exception, match="CHECK constraint failed"):
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO semantic_metrics (db_id, name, description, sql_template, status, created_at, updated_at)
                VALUES (1, 'test', 'test', 'test', 'bogus', datetime('now'), datetime('now'))
            """)
            )


def test_downgrade_converts_unverified_to_pending_approval(engine) -> None:
    """Downgrade converts unverified metrics to pending_approval before removing constraint."""
    _create_schema_with_constraint(engine)

    # Insert an unverified metric
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO semantic_metrics (db_id, name, description, sql_template, status, created_at, updated_at)
            VALUES (1, 'test', 'test', 'test', 'unverified', datetime('now'), datetime('now'))
        """)
        )

    # Simulate downgrade: convert unverified to pending_approval
    with engine.begin() as conn:
        conn.execute(
            text("""
            UPDATE semantic_metrics SET status = 'pending_approval' WHERE status = 'unverified'
        """)
        )

    # Verify conversion
    with engine.begin() as conn:
        result = conn.execute(text("SELECT status FROM semantic_metrics WHERE name = 'test'"))
        row = result.fetchone()
        assert row[0] == "pending_approval"


# ---------------------------------------------------------------------------
# Real-migration simulation (MigrationContext/Operations pattern)
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 1, 1)


def _create_pre_migration_schema(engine) -> None:
    """Create tables as they look at revision l7m8n9o0p1q2 (no status CHECK yet).

    semantic_metrics.status is deliberately nullable here so the NULL branch of
    the sanitizer can be exercised against dirtier legacy data.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE organization_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'member',
                joined_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_organization_members_org_user UNIQUE(org_id, user_id)
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE semantic_databases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER,
                created_by INTEGER,
                display_name VARCHAR(200) NOT NULL,
                db_type VARCHAR(50) NOT NULL,
                conn_url_enc TEXT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'draft',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE semantic_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id INTEGER NOT NULL,
                created_by INTEGER,
                name VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                sql_template TEXT NOT NULL,
                source VARCHAR(20) NOT NULL DEFAULT 'manual',
                status VARCHAR(20) DEFAULT 'draft',
                base_entity_id INTEGER,
                formula TEXT NOT NULL DEFAULT '',
                aggregation_type VARCHAR(50),
                definition JSON,
                version INTEGER NOT NULL DEFAULT 1,
                approved_by INTEGER,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        )


def _seed_outcome_matrix(conn) -> None:
    """Seed memberships, databases, and metrics covering every remap branch.

    Memberships: user 1 member / user 2 data_lead / user 3 admin of org 1;
    user 5 member of org 2 only; user 4 belongs to no workspace.
    Databases: 1 and 2 belong to org 1; database 3 is personal (org_id NULL).
    """
    memberships = [
        (1, 1, "member"),
        (1, 2, "data_lead"),
        (1, 3, "admin"),
        (2, 5, "member"),
    ]
    for org_id, user_id, role in memberships:
        conn.execute(
            text(
                "INSERT INTO organization_members (org_id, user_id, role, joined_at, updated_at) "
                "VALUES (:org_id, :user_id, :role, :now, :now)"
            ),
            {"org_id": org_id, "user_id": user_id, "role": role, "now": _NOW},
        )

    for db_id, org_id in [(1, 1), (2, 1), (3, None)]:
        conn.execute(
            text(
                "INSERT INTO semantic_databases (id, org_id, created_by, display_name, db_type, conn_url_enc, "
                "status, created_at, updated_at) VALUES (:id, :org_id, NULL, :name, 'postgres', 'enc', 'draft', :now, :now)"
            ),
            {"id": db_id, "org_id": org_id, "name": f"db{db_id}", "now": _NOW},
        )

    metrics = [
        ("m_member_pending", 1, 1, "pending_approval"),
        ("m_dl_pending", 1, 2, "pending_approval"),
        ("m_admin_pending", 1, 3, "pending_approval"),
        ("m_nonmember_pending", 1, 4, "pending_approval"),
        ("m_wrongorg_pending", 1, 5, "pending_approval"),
        ("m_personal_pending", 3, 1, "pending_approval"),
        ("m_invalid", 1, 1, "weird_status"),
        ("m_null_status", 1, 1, None),
        ("m_draft", 1, 1, "draft"),
        ("m_approved", 1, 1, "approved"),
        ("m_needs_review", 1, 1, "needs_review"),
        ("m_already_unverified", 1, 1, "unverified"),
        ("m_personal_invalid", 3, 1, "junk"),
    ]
    for name, db_id, created_by, status in metrics:
        conn.execute(
            text(
                "INSERT INTO semantic_metrics (db_id, created_by, name, description, sql_template, status, "
                "created_at, updated_at) VALUES (:db_id, :created_by, :name, 'd', 's', :status, :now, :now)"
            ),
            {"db_id": db_id, "created_by": created_by, "name": name, "status": status, "now": _NOW},
        )


def _status_of(db_engine, name: str) -> str | None:
    """Fetch the current status of one seeded metric by name."""
    with db_engine.connect() as conn:
        return conn.execute(text("SELECT status FROM semantic_metrics WHERE name = :name"), {"name": name}).scalar_one()


def _import_constrain_metric_status_migration():
    """Import the actual migration module from alembic/versions/."""
    import importlib.util
    import sys
    from pathlib import Path

    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*_constrain_metric_status.py"))
    if not migration_files:
        pytest.fail("Migration file '*_constrain_metric_status.py' not found in alembic/versions/.")

    spec = importlib.util.spec_from_file_location("_constrain_metric_status_migration", migration_files[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules["_constrain_metric_status_migration"] = module
    spec.loader.exec_module(module)
    return module


def _run_upgrade(db_engine) -> None:
    """Run the migration's upgrade() against the given engine."""
    module = _import_constrain_metric_status_migration()

    with db_engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with patch.object(module, "op", operations):
            module.upgrade()
        conn.commit()


def _run_downgrade(db_engine) -> None:
    """Run the migration's downgrade() against the given engine."""
    module = _import_constrain_metric_status_migration()

    with db_engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with patch.object(module, "op", operations):
            module.downgrade()
        conn.commit()


@pytest.fixture()
def remap_engine(tmp_path):
    """Yield a file-based SQLite engine carrying the pre-migration schema."""
    engine = create_engine(f"sqlite:///{tmp_path / 'metric_status_remap.db'}")
    _create_pre_migration_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_db(remap_engine):
    """Pre-migration engine seeded with the full outcome matrix."""
    with remap_engine.begin() as conn:
        _seed_outcome_matrix(conn)
    return remap_engine


class TestSanitizeAndRemapOutcomes:
    """upgrade() sanitizes legacy statuses, then remaps member-created pending metrics."""

    def test_member_created_pending_on_org_db_becomes_unverified(self, seeded_db):
        """Org DB + creator role member + pending_approval → unverified."""
        _run_upgrade(seeded_db)
        assert _status_of(seeded_db, "m_member_pending") == "unverified"

    def test_data_lead_and_admin_created_pending_stay_pending(self, seeded_db):
        """Org DB + creator role data_lead/admin → unchanged pending_approval."""
        _run_upgrade(seeded_db)
        assert _status_of(seeded_db, "m_dl_pending") == "pending_approval"
        assert _status_of(seeded_db, "m_admin_pending") == "pending_approval"

    def test_personal_db_metrics_are_never_remapped(self, seeded_db):
        """Personal DB (org_id IS NULL) → join never matches, status unchanged."""
        _run_upgrade(seeded_db)
        assert _status_of(seeded_db, "m_personal_pending") == "pending_approval"

    def test_invalid_and_null_statuses_become_needs_review(self, seeded_db):
        """Rows with NULL or non-whitelisted status → needs_review."""
        _run_upgrade(seeded_db)
        assert _status_of(seeded_db, "m_invalid") == "needs_review"
        assert _status_of(seeded_db, "m_null_status") == "needs_review"
        assert _status_of(seeded_db, "m_personal_invalid") == "needs_review"

    def test_valid_statuses_pass_through_unchanged(self, seeded_db):
        """Whitelisted statuses other than pending_approval are left alone."""
        _run_upgrade(seeded_db)
        assert _status_of(seeded_db, "m_draft") == "draft"
        assert _status_of(seeded_db, "m_approved") == "approved"
        assert _status_of(seeded_db, "m_needs_review") == "needs_review"
        assert _status_of(seeded_db, "m_already_unverified") == "unverified"

    def test_creator_without_matching_org_membership_stays_pending(self, seeded_db):
        """Creator outside the DB's workspace (no membership / wrong org) → unchanged."""
        _run_upgrade(seeded_db)
        assert _status_of(seeded_db, "m_nonmember_pending") == "pending_approval"
        assert _status_of(seeded_db, "m_wrongorg_pending") == "pending_approval"


class TestUpgradeStatementShape:
    """The upgrade must run exactly two UPDATE statements before adding the constraint."""

    def test_upgrade_issues_exactly_two_update_statements(self, remap_engine):
        with remap_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO semantic_databases (id, org_id, display_name, db_type, conn_url_enc, "
                    "status, created_at, updated_at) VALUES (1, 1, 'db', 'postgres', 'enc', 'draft', :now, :now)"
                ),
                {"now": _NOW},
            )
            conn.execute(
                text(
                    "INSERT INTO semantic_metrics (db_id, created_by, name, description, sql_template, status, "
                    "created_at, updated_at) VALUES (1, 7, 'm', 'd', 's', 'pending_approval', :now, :now)"
                ),
                {"now": _NOW},
            )

        statements: list[str] = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.strip().upper())

        sa.event.listen(remap_engine, "before_cursor_execute", capture)
        try:
            _run_upgrade(remap_engine)
        finally:
            sa.event.remove(remap_engine, "before_cursor_execute", capture)

        updates = [stmt for stmt in statements if stmt.startswith("UPDATE SEMANTIC_METRICS")]
        assert len(updates) == 2


class TestPostUpgradeConstraint:
    """After upgrade, the CHECK constraint must be active over sanitized data."""

    def test_constraint_rejects_unknown_status_after_upgrade(self, seeded_db):
        _run_upgrade(seeded_db)
        with pytest.raises(sa.exc.IntegrityError, match="CHECK constraint failed"):
            with seeded_db.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO semantic_metrics (db_id, created_by, name, description, sql_template, status, "
                        "created_at, updated_at) VALUES (1, 1, 'bogus', 'd', 's', 'bogus', :now, :now)"
                    ),
                    {"now": _NOW},
                )

    def test_constraint_accepts_every_valid_status_after_upgrade(self, seeded_db):
        _run_upgrade(seeded_db)
        valid = ["draft", "pending_approval", "approved", "needs_review", "unverified"]
        with seeded_db.begin() as conn:
            for idx, status in enumerate(valid, start=100):
                conn.execute(
                    text(
                        "INSERT INTO semantic_metrics (db_id, created_by, name, description, sql_template, status, "
                        "created_at, updated_at) VALUES (1, 1, :name, 'd', 's', :status, :now, :now)"
                    ),
                    {"name": f"valid_{idx}", "status": status, "now": _NOW},
                )


class TestDowngradeAfterRemap:
    """Downgrade still converts unverified back and removes the constraint."""

    def test_downgrade_reverts_unverified_and_drops_constraint(self, seeded_db):
        _run_upgrade(seeded_db)
        assert _status_of(seeded_db, "m_member_pending") == "unverified"

        _run_downgrade(seeded_db)

        assert _status_of(seeded_db, "m_member_pending") == "pending_approval"
        with seeded_db.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO semantic_metrics (db_id, created_by, name, description, sql_template, status, "
                    "created_at, updated_at) VALUES (1, 1, 'free', 'd', 's', 'anything_goes', :now, :now)"
                ),
                {"now": _NOW},
            )
