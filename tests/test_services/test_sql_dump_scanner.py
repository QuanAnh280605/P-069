"""Unit tests for the bounded SQL dump lexical scanner."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.models.schema_metadata import DiagnosticCode, SchemaDialect
from src.services.sql_dump_scanner import (
    ScannerLimits,
    SqlDumpScanError,
    StatementKind,
    scan_sql_dump,
)

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sql_dumps"
DEFAULT_LIMITS = ScannerLimits(
    max_file_bytes=20 * 1024 * 1024,
    max_statement_bytes=1024 * 1024,
    max_diagnostics=100,
    max_nesting_depth=128,
)


async def _chunks(payload: bytes, size: int) -> AsyncIterator[bytes]:
    for offset in range(0, len(payload), size):
        yield payload[offset : offset + size]


async def _scan(
    sql: str,
    *,
    chunk_size: int = 7,
    dialect: SchemaDialect | None = None,
    limits: ScannerLimits = DEFAULT_LIMITS,
    filename: str = "schema.sql",
):
    return await scan_sql_dump(
        _chunks(sql.encode("utf-8"), chunk_size),
        filename,
        limits,
        dialect,
    )


def _small_limits(**updates: int) -> ScannerLimits:
    values = {
        "max_file_bytes": 4096,
        "max_statement_bytes": 256,
        "max_diagnostics": 10,
        "max_nesting_depth": 8,
    }
    values.update(updates)
    return ScannerLimits(**values)


@pytest.mark.parametrize(
    ("fixture", "dialect", "statement_count"),
    [
        ("postgresql_schema.sql", SchemaDialect.POSTGRESQL, 10),
        ("mysql_schema.sql", SchemaDialect.MYSQL, 3),
    ],
)
@pytest.mark.parametrize("chunk_size", [1, 2, 7, 64, 65536])
async def test_real_dump_candidates_are_stable_across_chunk_boundaries(
    fixture: str,
    dialect: SchemaDialect,
    statement_count: int,
    chunk_size: int,
) -> None:
    payload = (FIXTURE_ROOT / fixture).read_bytes()

    result = await scan_sql_dump(_chunks(payload, chunk_size), fixture, DEFAULT_LIMITS)

    assert result.dialect == dialect
    assert len(result.statements) == statement_count
    assert all(item.kind in StatementKind for item in result.statements)
    assert not result.diagnostics


async def test_scanner_output_is_deterministic_for_same_dump() -> None:
    payload = (FIXTURE_ROOT / "postgresql_schema.sql").read_bytes()

    bytewise = await scan_sql_dump(_chunks(payload, 1), "dump.SQL", DEFAULT_LIMITS)
    blockwise = await scan_sql_dump(_chunks(payload, 4096), "dump.SQL", DEFAULT_LIMITS)

    assert bytewise == blockwise


@pytest.mark.parametrize("payload", [b"", b"\xef\xbb\xbf"])
async def test_empty_or_bom_only_file_is_rejected(payload: bytes) -> None:
    with pytest.raises(SqlDumpScanError) as raised:
        await scan_sql_dump(_chunks(payload, 1), "empty.sql", DEFAULT_LIMITS)

    assert raised.value.diagnostic.code == DiagnosticCode.EMPTY_FILE


async def test_utf8_bom_and_split_multibyte_identifier_are_supported() -> None:
    sql = '\ufeff-- PostgreSQL database dump\nCREATE TABLE "??n h?ng" (id integer);'

    result = await _scan(sql, chunk_size=1, filename="SCHEMA.SQL")

    assert result.statements[0].text.endswith('"??n h?ng" (id integer)')


async def test_invalid_extension_is_rejected_case_insensitively() -> None:
    with pytest.raises(SqlDumpScanError) as raised:
        await _scan("CREATE TABLE x (id int);", filename="schema.txt")

    assert raised.value.diagnostic.code == DiagnosticCode.INVALID_EXTENSION


async def test_invalid_utf8_is_rejected_without_echoing_bytes() -> None:
    with pytest.raises(SqlDumpScanError) as raised:
        await scan_sql_dump(_chunks(b"\xffsecret", 1), "schema.sql", DEFAULT_LIMITS)

    assert raised.value.diagnostic.code == DiagnosticCode.INVALID_ENCODING
    assert "secret" not in str(raised.value)


async def test_file_limit_is_checked_while_streaming() -> None:
    limits = _small_limits(max_file_bytes=10)

    with pytest.raises(SqlDumpScanError) as raised:
        await _scan("CREATE TABLE x (id int);", limits=limits, chunk_size=3)

    assert raised.value.diagnostic.code == DiagnosticCode.FILE_TOO_LARGE


def test_release_tested_hard_maxima_cannot_be_raised() -> None:
    with pytest.raises(ValidationError):
        ScannerLimits(
            max_file_bytes=20 * 1024 * 1024 + 1,
            max_statement_bytes=1024 * 1024,
            max_diagnostics=100,
            max_nesting_depth=128,
        )


async def test_postgresql_lexical_states_do_not_split_on_inner_semicolons() -> None:
    sql = """-- PostgreSQL database dump
CREATE SCHEMA app;
CREATE TABLE app."Odd;Name" (
 id integer,
 label text DEFAULT 'it''s;safe',
 expression text DEFAULT $tag$(a; b)$tag$,
 score integer DEFAULT ((1 + (2))); -- comment ; ignored
);
ALTER TABLE ONLY app."Odd;Name" ADD PRIMARY KEY (id);
"""

    result = await _scan(sql, chunk_size=1)

    assert [item.kind for item in result.statements] == [
        StatementKind.CREATE_SCHEMA,
        StatementKind.CREATE_TABLE,
        StatementKind.ALTER_TABLE,
    ]
    assert result.statements[0].line == 2


async def test_mysql_backticks_and_semicolon_literal_are_preserved() -> None:
    sql = "CREATE TABLE `Odd;Name` (`value` varchar(20) DEFAULT 'a;b');"

    result = await _scan(sql, chunk_size=1, dialect=SchemaDialect.MYSQL)

    assert len(result.statements) == 1
    assert "`Odd;Name`" in result.statements[0].text


async def test_copy_and_insert_payloads_are_never_emitted() -> None:
    secret = "customer-secret-123"
    template = """-- PostgreSQL database dump
CREATE TABLE public.accounts (id integer);
COPY public.accounts (id) FROM stdin;
1\t__SECRET__
\\.
INSERT INTO public.accounts VALUES (2, '__SECRET__');
ALTER TABLE ONLY public.accounts ADD PRIMARY KEY (id);
"""
    sql = template.replace("__SECRET__", secret).replace("\n", "\r\n")

    result = await _scan(sql, chunk_size=1)

    serialized = result.model_dump_json()
    assert secret not in serialized
    assert [item.kind for item in result.statements] == [StatementKind.CREATE_TABLE, StatementKind.ALTER_TABLE]
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.DATA_STATEMENTS_IGNORED]


async def test_long_skipped_dml_does_not_use_retained_ddl_limit() -> None:
    long_value = "s" * 2000
    sql = "INSERT INTO x VALUES ('__VALUE__'); CREATE TABLE x (id int);".replace("__VALUE__", long_value)
    limits = _small_limits(max_statement_bytes=64)

    result = await _scan(sql, dialect=SchemaDialect.POSTGRESQL, limits=limits)

    assert len(result.statements) == 1
    assert long_value not in result.model_dump_json()


async def test_mysql_version_comments_and_custom_delimiter_are_skipped() -> None:
    sql = """-- MySQL dump
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
DELIMITER $$
CREATE PROCEDURE ignored_proc() BEGIN SELECT 'a;b'; END$$
DELIMITER ;
SET sql_mode = '';
CREATE TABLE `kept` (`id` int);
"""

    result = await _scan(sql, chunk_size=1)

    assert result.dialect == SchemaDialect.MYSQL
    assert [item.kind for item in result.statements] == [StatementKind.CREATE_TABLE]
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.UNSUPPORTED_STATEMENT]


async def test_unsupported_postgresql_dollar_body_does_not_split_following_ddl() -> None:
    sql = """-- PostgreSQL database dump
CREATE FUNCTION ignored() RETURNS void AS $$ BEGIN PERFORM 1; PERFORM 2; END $$ LANGUAGE plpgsql;
CREATE TABLE kept (id integer);
"""

    result = await _scan(sql, chunk_size=1)

    assert [item.kind for item in result.statements] == [StatementKind.CREATE_TABLE]
    assert [item.code for item in result.diagnostics] == [DiagnosticCode.UNSUPPORTED_STATEMENT]


async def test_explicit_dialect_resolves_generic_ddl() -> None:
    result = await _scan("CREATE TABLE plain (id integer);", dialect=SchemaDialect.POSTGRESQL)

    assert result.dialect == SchemaDialect.POSTGRESQL


async def test_postgresql_ownership_alters_are_safe_noncore_warnings() -> None:
    sql = """-- PostgreSQL database dump
CREATE TABLE public.accounts (id integer);
ALTER TABLE public.accounts OWNER TO postgres;
ALTER TABLE public.accounts_id_seq OWNER TO postgres;
"""

    result = await _scan(sql)

    assert [item.kind for item in result.statements] == [StatementKind.CREATE_TABLE]
    assert [item.message for item in result.diagnostics] == [
        "Object ownership statement was ignored",
        "Object ownership statement was ignored",
    ]


async def test_ambiguous_dialect_is_not_guessed() -> None:
    with pytest.raises(SqlDumpScanError) as raised:
        await _scan("CREATE TABLE plain (id integer);")

    assert raised.value.diagnostic.code == DiagnosticCode.DIALECT_AMBIGUOUS


@pytest.mark.parametrize(
    "sql",
    [
        "-- PostgreSQL database dump\n-- MySQL dump\nCREATE TABLE x (id int);",
        "-- PostgreSQL database dump\nCREATE TABLE `x` (id int);",
    ],
)
async def test_mixed_dialect_evidence_is_fatal(sql: str) -> None:
    with pytest.raises(SqlDumpScanError) as raised:
        await _scan(sql)

    assert raised.value.diagnostic.code == DiagnosticCode.DIALECT_CONFLICT


async def test_override_conflicting_with_evidence_is_fatal() -> None:
    sql = "-- PostgreSQL database dump\nCREATE TABLE x (id int);"

    with pytest.raises(SqlDumpScanError) as raised:
        await _scan(sql, dialect=SchemaDialect.MYSQL)

    assert raised.value.diagnostic.code == DiagnosticCode.DIALECT_CONFLICT


async def test_retained_ddl_statement_limit_is_fatal() -> None:
    sql = f"CREATE TABLE x ({'long_name integer, ' * 10}id integer);"

    with pytest.raises(SqlDumpScanError) as raised:
        await _scan(sql, dialect=SchemaDialect.POSTGRESQL, limits=_small_limits(max_statement_bytes=64))

    assert raised.value.diagnostic.code == DiagnosticCode.STATEMENT_TOO_LARGE


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE x (value text DEFAULT 'unfinished",
        'CREATE TABLE "unfinished (id integer);',
        "CREATE TABLE x (id integer); /* unfinished",
        "CREATE TABLE x (value text DEFAULT $tag$unfinished",
        "CREATE TABLE x ((id integer);",
        "COPY x FROM stdin;\nsecret\n",
    ],
)
async def test_unbalanced_eof_state_is_fatal(sql: str) -> None:
    with pytest.raises(SqlDumpScanError) as raised:
        await _scan(sql, dialect=SchemaDialect.POSTGRESQL)

    assert raised.value.diagnostic.code == DiagnosticCode.DDL_PARSE_ERROR


async def test_nesting_depth_limit_is_fatal() -> None:
    sql = "CREATE TABLE x (value integer DEFAULT (((1))));"

    with pytest.raises(SqlDumpScanError) as raised:
        await _scan(sql, dialect=SchemaDialect.POSTGRESQL, limits=_small_limits(max_nesting_depth=2))

    assert raised.value.diagnostic.code == DiagnosticCode.DDL_PARSE_ERROR


async def test_diagnostic_count_is_bounded() -> None:
    sql = "CREATE VIEW a AS SELECT 1; CREATE VIEW b AS SELECT 1; CREATE VIEW c AS SELECT 1; CREATE TABLE x (id int);"

    result = await _scan(
        sql,
        dialect=SchemaDialect.POSTGRESQL,
        limits=_small_limits(max_diagnostics=2),
    )

    assert len(result.diagnostics) == 2
    assert all(item.code == DiagnosticCode.UNSUPPORTED_STATEMENT for item in result.diagnostics)


async def test_data_only_dump_is_rejected_without_payload_in_error() -> None:
    secret = "do-not-echo-this"

    with pytest.raises(SqlDumpScanError) as raised:
        sql = "INSERT INTO x VALUES ('__SECRET__');".replace("__SECRET__", secret)
        await _scan(sql, dialect=SchemaDialect.MYSQL)

    assert raised.value.diagnostic.code == DiagnosticCode.NO_SUPPORTED_DDL
    assert secret not in str(raised.value)
