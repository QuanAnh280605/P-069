"""Contract tests for vendor-generated SQL dump fixtures."""

from pathlib import Path

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sql_dumps"
POSTGRESQL_FIXTURE = FIXTURE_ROOT / "postgresql_schema.sql"
MYSQL_FIXTURE = FIXTURE_ROOT / "mysql_schema.sql"
POSTGRESQL_SOURCE = FIXTURE_ROOT / "source" / "postgresql_fixture_source.sql"
MYSQL_SOURCE = FIXTURE_ROOT / "source" / "mysql_fixture_source.sql"
PROVENANCE = FIXTURE_ROOT / "README.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_postgresql_fixture_has_vendor_provenance_and_real_envelope() -> None:
    dump = _read(POSTGRESQL_FIXTURE)
    provenance = _read(PROVENANCE)

    assert "Dumped by pg_dump version 16.14" in dump
    assert "`pg_dump` 16.14" in provenance
    assert "--schema-only" in provenance
    assert "fixture_restrict_key" in dump


def test_postgresql_fixture_covers_phase_two_schema_features() -> None:
    dump = _read(POSTGRESQL_FIXTURE)

    assert dump.count("CREATE TABLE") == 3
    assert "PRIMARY KEY (tenant_id, customer_id)" in dump
    assert "FOREIGN KEY (tenant_id, order_id)" in dump
    assert 'audit."Order Events"' in dump
    assert '"Event Type"' in dump
    assert "DEFAULT CURRENT_TIMESTAMP NOT NULL" in dump
    assert "nickname text" in dump
    assert dump.count("ALTER TABLE ONLY") >= 5


def test_postgresql_golden_fixture_contains_no_row_data() -> None:
    dump = _read(POSTGRESQL_FIXTURE).upper()

    assert "INSERT INTO" not in dump
    assert "COPY " not in dump


def test_generation_sources_cover_both_dialects_without_row_data() -> None:
    postgresql = _read(POSTGRESQL_SOURCE)
    mysql = _read(MYSQL_SOURCE)

    assert "ALTER TABLE ONLY" in postgresql
    assert "ALTER TABLE `Order Events`" in mysql
    assert "`Event Type`" in mysql
    assert "FOREIGN KEY" in postgresql and "FOREIGN KEY" in mysql
    assert "INSERT INTO" not in postgresql.upper()
    assert "INSERT INTO" not in mysql.upper()


def test_mysql_fixture_has_vendor_provenance_and_real_envelope() -> None:
    dump = _read(MYSQL_FIXTURE)
    provenance = _read(PROVENANCE)

    assert "MySQL dump 10.13  Distrib 8.0.46" in dump
    assert "`mysqldump` 8.0.46" in provenance
    assert "--no-data" in provenance
    assert "CREATE TABLE `Customers`" in dump
    assert "CREATE TABLE `Order Events`" in dump


def test_mysql_fixture_covers_phase_two_schema_features() -> None:
    dump = _read(MYSQL_FIXTURE)

    assert dump.count("CREATE TABLE") == 3
    assert "PRIMARY KEY (`tenant_id`,`customer_id`)" in dump
    assert "FOREIGN KEY (`tenant_id`, `order_id`)" in dump
    assert "`Event Type` varchar(40) NOT NULL DEFAULT 'created'" in dump
    assert "`nickname` varchar(120) DEFAULT NULL" in dump


def test_mysql_golden_fixture_contains_no_row_data() -> None:
    dump = _read(MYSQL_FIXTURE).upper()

    assert "INSERT INTO" not in dump
    assert "LOCK TABLES" not in dump
