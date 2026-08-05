"""Golden and strict-policy tests for SQL dump AST extraction."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from src.models.schema_metadata import (
    DiagnosticCode,
    ParseCompleteness,
    SchemaDialect,
)
from src.services.sql_dump_parser import SqlDumpParseError, parse_sql_dump
from src.services.sql_dump_scanner import scan_sql_dump
from src.services.sql_dump_scanner_models import ScannedStatement, ScannerLimits, ScanResult, StatementKind

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sql_dumps"


async def _chunks(payload: bytes, size: int = 17) -> AsyncIterator[bytes]:
    for offset in range(0, len(payload), size):
        yield payload[offset : offset + size]


async def _parse_text(sql: str, dialect: SchemaDialect):
    scan = await scan_sql_dump(
        _chunks(sql.encode("utf-8")),
        "schema.sql",
        dialect_override=dialect,
    )
    return await parse_sql_dump(scan)


async def _parse_fixture(filename: str):
    payload = (FIXTURE_ROOT / filename).read_bytes()
    scan = await scan_sql_dump(_chunks(payload), filename)
    return await parse_sql_dump(scan)


def _column_projection(table) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            column.column_name.raw_name,
            column.column_name.normalized_name,
            column.column_name.quoted,
            column.raw_data_type,
            column.data_type,
            column.nullable,
            column.default_expression,
            column.primary_key,
        )
        for column in table.columns
    )


def _key_projection(table) -> tuple[object, ...]:
    primary = table.primary_key
    primary_columns = tuple(item.raw_name for item in primary.constrained_columns) if primary else ()
    primary_name = primary.constraint_name.raw_name if primary and primary.constraint_name else None
    foreign = tuple(
        (
            item.constraint_name.raw_name if item.constraint_name else None,
            tuple(column.raw_name for column in item.constrained_columns),
            item.referred_schema.raw_name,
            item.referred_table.raw_name,
            tuple(column.raw_name for column in item.referred_columns),
        )
        for item in table.foreign_keys
    )
    return primary_name, primary_columns, foreign


async def test_postgresql_golden_dump_matches_exact_core_ir() -> None:
    result = await _parse_fixture("postgresql_schema.sql")
    tables = {table.table_name.raw_name: table for table in result.schema_metadata.tables}

    assert result.completeness == ParseCompleteness.COMPLETE
    assert result.schema_metadata.dialect == SchemaDialect.POSTGRESQL
    assert [item.schema_name.raw_name for item in result.schema_metadata.schemas] == ["audit", "sales"]
    assert _column_projection(tables["Order Events"]) == (
        ("event_id", "event_id", False, "BIGINT", "BIGINT", False, None, True),
        ("tenant_id", "tenant_id", False, "BIGINT", "BIGINT", False, None, False),
        ("order_id", "order_id", False, "BIGINT", "BIGINT", False, None, False),
        ("Event Type", "Event Type", True, "VARCHAR(40)", "VARCHAR(40)", False, "CAST('created' AS VARCHAR)", False),
        ("details", "details", False, "JSONB", "JSONB", True, None, False),
    )
    assert _key_projection(tables["Order Events"]) == (
        "order_events_pkey",
        ("event_id",),
        (("order_events_order_fk", ("tenant_id", "order_id"), "sales", "orders", ("tenant_id", "order_id")),),
    )


async def test_postgresql_golden_composite_keys_defaults_and_order_are_exact() -> None:
    result = await _parse_fixture("postgresql_schema.sql")
    tables = {table.table_name.raw_name: table for table in result.schema_metadata.tables}

    assert _column_projection(tables["customers"]) == (
        ("tenant_id", "tenant_id", False, "BIGINT", "BIGINT", False, None, True),
        ("customer_id", "customer_id", False, "BIGINT", "BIGINT", False, None, True),
        ("display_name", "display_name", False, "VARCHAR(120)", "VARCHAR(120)", False, None, False),
        ("nickname", "nickname", False, "TEXT", "TEXT", True, None, False),
        ("created_at", "created_at", False, "TIMESTAMPTZ", "TIMESTAMPTZ", False, "CURRENT_TIMESTAMP", False),
    )
    assert _key_projection(tables["orders"]) == (
        "orders_pkey",
        ("tenant_id", "order_id"),
        (("orders_customer_fk", ("tenant_id", "customer_id"), "sales", "customers", ("tenant_id", "customer_id")),),
    )


async def test_mysql_golden_dump_matches_exact_core_ir() -> None:
    result = await _parse_fixture("mysql_schema.sql")
    tables = {table.table_name.raw_name: table for table in result.schema_metadata.tables}

    assert result.completeness == ParseCompleteness.COMPLETE
    assert [item.schema_name.raw_name for item in result.schema_metadata.schemas] == ["__default__"]
    assert _column_projection(tables["Customers"]) == (
        ("tenant_id", "tenant_id", True, "BIGINT", "BIGINT", False, None, True),
        ("customer_id", "customer_id", True, "BIGINT", "BIGINT", False, None, True),
        ("display_name", "display_name", True, "VARCHAR(120)", "VARCHAR(120)", False, None, False),
        ("nickname", "nickname", True, "VARCHAR(120)", "VARCHAR(120)", True, "NULL", False),
        ("created_at", "created_at", True, "TIMESTAMP", "TIMESTAMPTZ", False, "CURRENT_TIMESTAMP()", False),
    )
    assert _key_projection(tables["orders"]) == (
        None,
        ("tenant_id", "order_id"),
        (
            (
                "orders_customer_fk",
                ("tenant_id", "customer_id"),
                "__default__",
                "Customers",
                ("tenant_id", "customer_id"),
            ),
        ),
    )


async def test_pg_dump_ownership_and_altered_sequence_defaults_are_supported() -> None:
    result = await _parse_fixture("postgresql_dump_schema.sql")
    tables = {table.table_name.raw_name: table for table in result.schema_metadata.tables}

    assert result.completeness == ParseCompleteness.COMPLETE
    assert [table.table_name.raw_name for table in result.schema_metadata.tables] == [
        "categories",
        "products",
        "users",
    ]
    assert tables["users"].columns[0].default_expression == ("NEXTVAL(CAST('public.users_user_id_seq' AS REGCLASS))")
    assert tables["categories"].columns[0].default_expression == (
        "NEXTVAL(CAST('public.categories_category_id_seq' AS REGCLASS))"
    )
    assert tables["products"].columns[0].default_expression == (
        "NEXTVAL(CAST('public.products_product_id_seq' AS REGCLASS))"
    )


async def test_alter_column_default_requires_an_existing_column() -> None:
    sql = "CREATE TABLE x (id int); ALTER TABLE x ALTER COLUMN missing SET DEFAULT 1;"

    with pytest.raises(SqlDumpParseError) as raised:
        await _parse_text(sql, SchemaDialect.POSTGRESQL)

    assert raised.value.diagnostic.code == DiagnosticCode.DDL_PARSE_ERROR
    assert raised.value.diagnostic.message == "ALTER COLUMN references an unknown column"


async def test_mysql_dialect_types_preserve_safe_raw_and_normalized_text() -> None:
    sql = "CREATE TABLE `typed` (`unsigned_id` int unsigned, `size` enum('small','large'), `created` timestamp);"

    result = await _parse_text(sql, SchemaDialect.MYSQL)
    columns = result.schema_metadata.tables[0].columns

    assert [(item.raw_data_type, item.data_type) for item in columns] == [
        ("INT UNSIGNED", "UINT"),
        ("ENUM('small', 'large')", "ENUM('small', 'large')"),
        ("TIMESTAMP", "TIMESTAMPTZ"),
    ]


async def test_inline_table_and_alter_constraints_use_two_pass_resolution() -> None:
    sql = """ALTER TABLE child ADD CONSTRAINT child_parent_fk FOREIGN KEY (tenant_id, parent_id) REFERENCES parent(tenant_id, parent_id);
CREATE TABLE child (tenant_id int, parent_id int, local_id int PRIMARY KEY);
CREATE TABLE parent (tenant_id int, parent_id int, PRIMARY KEY (tenant_id, parent_id));
"""

    result = await _parse_text(sql, SchemaDialect.POSTGRESQL)
    child = next(item for item in result.schema_metadata.tables if item.table_name.raw_name == "child")

    assert _key_projection(child) == (
        None,
        ("local_id",),
        (("child_parent_fk", ("tenant_id", "parent_id"), "public", "parent", ("tenant_id", "parent_id")),),
    )


async def test_inline_reference_resolves_table_declared_later() -> None:
    sql = "CREATE TABLE child (id int PRIMARY KEY, parent_id int REFERENCES parent(id)); CREATE TABLE parent (id int PRIMARY KEY);"

    result = await _parse_text(sql, SchemaDialect.POSTGRESQL)
    child = result.schema_metadata.tables[0]

    assert child.foreign_keys[0].constrained_columns[0].raw_name == "parent_id"
    assert child.foreign_keys[0].referred_table.raw_name == "parent"


async def test_same_quoted_table_name_in_two_schemas_does_not_collide() -> None:
    sql = 'CREATE SCHEMA a; CREATE SCHEMA b; CREATE TABLE a."Shared" (id int); CREATE TABLE b."Shared" (id int);'

    result = await _parse_text(sql, SchemaDialect.POSTGRESQL)

    assert [item.qualified_identity.canonical_key for item in result.schema_metadata.tables] == [
        ("a", "Shared"),
        ("b", "Shared"),
    ]


async def test_mysql_qualified_database_names_are_preserved_as_schemas() -> None:
    sql = "CREATE TABLE `catalog_a`.`shared` (`id` int); CREATE TABLE `catalog_b`.`shared` (`id` int);"

    result = await _parse_text(sql, SchemaDialect.MYSQL)

    assert [item.qualified_identity.canonical_key for item in result.schema_metadata.tables] == [
        ("catalog_a", "shared"),
        ("catalog_b", "shared"),
    ]


async def test_mysql_use_context_applies_to_unqualified_tables_and_alters() -> None:
    sql = "USE `Sales Catalog`; CREATE TABLE parent (id int PRIMARY KEY); CREATE TABLE child (pid int); ALTER TABLE child ADD FOREIGN KEY(pid) REFERENCES parent(id);"

    result = await _parse_text(sql, SchemaDialect.MYSQL)

    assert [item.schema_name.raw_name for item in result.schema_metadata.schemas] == ["Sales Catalog"]
    assert all(item.schema_name.quoted for item in result.schema_metadata.tables)
    child = next(item for item in result.schema_metadata.tables if item.table_name.raw_name == "child")
    assert child.foreign_keys[0].referred_schema.raw_name == "Sales Catalog"


async def test_unquoted_and_quoted_identifier_matching_is_exact_without_fuzzy_match() -> None:
    sql = 'CREATE TABLE "Parent" ("ID" int PRIMARY KEY); CREATE TABLE child (parent_id int REFERENCES "Parent"("ID"));'

    result = await _parse_text(sql, SchemaDialect.POSTGRESQL)
    child = next(item for item in result.schema_metadata.tables if item.table_name.raw_name == "child")

    assert child.foreign_keys[0].referred_table.normalized_name == "Parent"
    assert child.foreign_keys[0].referred_columns[0].normalized_name == "ID"


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("CREATE TABLE x (id int); CREATE TABLE X (other int);", DiagnosticCode.DUPLICATE_OBJECT),
        ("CREATE TABLE x (id int, ID text);", DiagnosticCode.DUPLICATE_OBJECT),
        ("CREATE TABLE x (id int PRIMARY KEY, PRIMARY KEY(id));", DiagnosticCode.CONFLICTING_CONSTRAINT),
        (
            "CREATE TABLE p (a int, b int); CREATE TABLE c (a int, FOREIGN KEY(a) REFERENCES p(a,b));",
            DiagnosticCode.CONFLICTING_CONSTRAINT,
        ),
        (
            "CREATE TABLE p (id int); CREATE TABLE c (pid int, FOREIGN KEY(pid) REFERENCES p(id), FOREIGN KEY(pid) REFERENCES p(id));",
            DiagnosticCode.CONFLICTING_CONSTRAINT,
        ),
        (
            "CREATE TABLE p (id int); CREATE TABLE c (id int, pid int, CONSTRAINT same PRIMARY KEY(id), CONSTRAINT same FOREIGN KEY(pid) REFERENCES p(id));",
            DiagnosticCode.CONFLICTING_CONSTRAINT,
        ),
        ("CREATE TABLE c (a int, FOREIGN KEY(a) REFERENCES missing(a));", DiagnosticCode.UNRESOLVED_FOREIGN_KEY),
        ("CREATE TABLE x (id int); ALTER TABLE x ADD COLUMN extra int;", DiagnosticCode.DDL_PARSE_ERROR),
        ("CREATE TABLE x (id);", DiagnosticCode.DDL_PARSE_ERROR),
        ("CREATE TABLE x ();", DiagnosticCode.DDL_PARSE_ERROR),
    ],
)
async def test_strict_core_failures_raise_stable_diagnostic(sql: str, code: DiagnosticCode) -> None:
    with pytest.raises(SqlDumpParseError) as raised:
        await _parse_text(sql, SchemaDialect.POSTGRESQL)

    assert raised.value.diagnostic.code == code
    assert raised.value.diagnostic.recoverable is False


async def test_unresolved_case_difference_is_not_fuzzy_matched() -> None:
    sql = 'CREATE TABLE "Parent" (id int); CREATE TABLE child (parent_id int REFERENCES parent(id));'

    with pytest.raises(SqlDumpParseError) as raised:
        await _parse_text(sql, SchemaDialect.POSTGRESQL)

    assert raised.value.diagnostic.code == DiagnosticCode.UNRESOLVED_FOREIGN_KEY


async def test_noncore_alter_constraint_is_warning_and_keeps_complete_ir() -> None:
    sql = "CREATE TABLE x (id int); ALTER TABLE x ADD CONSTRAINT positive CHECK (id > 0);"

    result = await _parse_text(sql, SchemaDialect.POSTGRESQL)

    assert result.completeness == ParseCompleteness.COMPLETE
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.UNSUPPORTED_STATEMENT]


async def test_scanner_diagnostics_are_preserved_outside_domain_schema() -> None:
    sql = "INSERT INTO x VALUES (99); CREATE TABLE x (id int);"

    result = await _parse_text(sql, SchemaDialect.MYSQL)

    assert [item.code for item in result.diagnostics] == [DiagnosticCode.DATA_STATEMENTS_IGNORED]
    assert "diagnostics" not in result.schema_metadata.model_dump()


async def test_command_fallback_is_fatal_and_never_logs_raw_ddl(caplog: pytest.LogCaptureFixture) -> None:
    secret_identifier = "private_identifier_xyz"
    statement = ScannedStatement(
        text=f"ALTER TABLE {secret_identifier} ADD PRIMARY KEY (id), ADD FOREIGN KEY (pid) REFERENCES parent(id)",
        kind=StatementKind.ALTER_TABLE,
        statement_index=0,
        line=1,
        column=1,
    )
    scan = ScanResult(dialect=SchemaDialect.POSTGRESQL, statements=(statement,), total_bytes=len(statement.text))

    with pytest.raises(SqlDumpParseError) as raised:
        await parse_sql_dump(scan)

    assert raised.value.diagnostic.code == DiagnosticCode.UNSUPPORTED_STATEMENT
    assert secret_identifier not in caplog.text
    assert secret_identifier not in str(raised.value)


async def test_foreign_key_actions_are_reported_without_losing_mapping() -> None:
    sql = "CREATE TABLE parent (id int PRIMARY KEY); CREATE TABLE child (pid int REFERENCES parent(id) ON DELETE CASCADE);"

    result = await _parse_text(sql, SchemaDialect.POSTGRESQL)

    child = next(item for item in result.schema_metadata.tables if item.table_name.raw_name == "child")
    assert child.foreign_keys[0].referred_table.raw_name == "parent"
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.UNSUPPORTED_STATEMENT]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE x (a int, PRIMARY KEY(a, a));",
        "CREATE TABLE p (a int, b int); CREATE TABLE c (a int, b int, FOREIGN KEY(a, a) REFERENCES p(a, b));",
        "CREATE TABLE p (a int, b int); CREATE TABLE c (a int, b int, FOREIGN KEY(a, b) REFERENCES p(a, a));",
    ],
)
async def test_repeated_constraint_columns_are_stable_fatal_errors(sql: str) -> None:
    with pytest.raises(SqlDumpParseError) as raised:
        await _parse_text(sql, SchemaDialect.POSTGRESQL)

    assert raised.value.diagnostic.code == DiagnosticCode.CONFLICTING_CONSTRAINT


async def test_parser_result_is_deterministic() -> None:
    first = await _parse_fixture("postgresql_schema.sql")
    second = await _parse_fixture("postgresql_schema.sql")

    assert first == second


async def test_parser_diagnostic_count_respects_scanner_envelope_limit() -> None:
    sql = """CREATE TABLE x (id int);
ALTER TABLE x ADD CONSTRAINT check_a CHECK (id > 0);
ALTER TABLE x ADD CONSTRAINT check_b CHECK (id > 1);
ALTER TABLE x ADD CONSTRAINT check_c CHECK (id > 2);
"""
    scan = await scan_sql_dump(
        _chunks(sql.encode("utf-8")),
        "schema.sql",
        limits=ScannerLimits(
            max_file_bytes=4096,
            max_statement_bytes=1024,
            max_diagnostics=2,
            max_nesting_depth=32,
        ),
        dialect_override=SchemaDialect.POSTGRESQL,
    )

    result = await parse_sql_dump(scan)

    assert len(result.diagnostics) == 2


def test_parser_core_has_no_database_llm_or_execution_dependency() -> None:
    source = (Path(__file__).parents[2] / "src" / "services" / "sql_dump_parser.py").read_text(encoding="utf-8")

    assert "sqlalchemy" not in source
    assert "get_llm" not in source
    assert "subprocess" not in source
    assert ".execute(" not in source
