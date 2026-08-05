"""SQLGlot compatibility spike for the Phase 2 DDL corpus."""

import re
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "sql_dumps"
DDL_PATTERN = re.compile(r"(?ms)^(?:CREATE (?:SCHEMA|TABLE)|ALTER TABLE).*?;")


def _read(relative_path: str) -> str:
    return (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")


def _parse_fixture_ddl(relative_path: str, dialect: str) -> list[exp.Expression]:
    statements = DDL_PATTERN.findall(_read(relative_path))
    return [sqlglot.parse_one(statement, read=dialect) for statement in statements]


def test_candidate_version_is_pinned() -> None:
    assert sqlglot.__version__ == "30.13.0"


def test_full_postgresql_dump_envelope_requires_scanner() -> None:
    with pytest.raises(ParseError, match="Unexpected token"):
        sqlglot.parse(_read("postgresql_schema.sql"), read="postgres")


def test_postgresql_golden_core_ddl_has_supported_ast_nodes() -> None:
    expressions = _parse_fixture_ddl("postgresql_schema.sql", "postgres")

    assert len(expressions) == 10
    assert all(isinstance(item, (exp.Create, exp.Alter)) for item in expressions)
    assert not any(isinstance(item, exp.Command) for item in expressions)
    assert sum(1 for item in expressions if isinstance(item, exp.Alter)) == 5
    assert all(item.args["only"] for item in expressions if isinstance(item, exp.Alter))


def test_postgresql_alter_fk_preserves_quoted_and_composite_identity() -> None:
    expressions = _parse_fixture_ddl("postgresql_schema.sql", "postgres")
    order_event_fk = next(item for item in expressions if item.find(exp.ForeignKey))
    table = order_event_fk.this
    foreign_key = order_event_fk.find(exp.ForeignKey)

    assert isinstance(table, exp.Table)
    assert table.name == "Order Events" and table.this.args["quoted"] is True
    assert foreign_key is not None
    assert [column.name for column in foreign_key.expressions] == ["tenant_id", "order_id"]


def test_mysql_golden_core_ddl_has_supported_ast_nodes() -> None:
    expressions = _parse_fixture_ddl("mysql_schema.sql", "mysql")

    assert len(expressions) == 3
    assert all(isinstance(item, exp.Create) for item in expressions)
    assert not any(isinstance(item, exp.Command) for item in expressions)
    assert expressions[1].this.this.name == "Order Events"
    assert expressions[1].this.this.this.args["quoted"] is True


def test_mysql_source_alter_has_supported_ast_node() -> None:
    expressions = sqlglot.parse(_read("source/mysql_fixture_source.sql"), read="mysql")
    core = [item for item in expressions if isinstance(item, (exp.Create, exp.Alter))]

    assert len(core) == 5
    assert not any(isinstance(item, exp.Command) for item in expressions)
    assert isinstance(core[-1], exp.Alter)
    assert core[-1].this.name == "Order Events"
    assert core[-1].this.this.args["quoted"] is True


def test_mysql_timestamp_ast_requires_raw_type_preservation() -> None:
    expressions = _parse_fixture_ddl("mysql_schema.sql", "mysql")
    customers = next(
        item for item in expressions if isinstance(item, exp.Create) and item.this.this.name == "Customers"
    )
    created_at = next(column for column in customers.find_all(exp.ColumnDef) if column.name == "created_at")

    assert created_at.args["kind"].this == exp.DataType.Type.TIMESTAMPTZ
    assert "timestamp" in _read("mysql_schema.sql").lower()
