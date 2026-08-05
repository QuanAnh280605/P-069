"""Tests for the persistence-free canonical schema metadata contract."""

import pytest
from pydantic import ValidationError

from src.models.schema_metadata import (
    ColumnMetadata,
    DiagnosticCode,
    DiagnosticSeverity,
    ForeignKeyMetadata,
    Identifier,
    ParseCompleteness,
    ParseDiagnostic,
    ParseResult,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
    default_schema_identifier,
)

DIALECT = SchemaDialect.POSTGRESQL


def identifier(name: str, quoted: bool = False) -> Identifier:
    """Build a PostgreSQL identifier for concise contract tests."""
    return Identifier.from_raw(name, DIALECT, quoted)


def column(name: str, position: int, primary_key: bool = False) -> ColumnMetadata:
    """Build a representative canonical column."""
    return ColumnMetadata(
        column_name=identifier(name),
        ordinal_position=position,
        raw_data_type="integer",
        data_type="INTEGER",
        nullable=not primary_key,
        default_expression=None,
        primary_key=primary_key,
    )


def table(schema: str, name: str, columns: tuple[ColumnMetadata, ...]) -> TableMetadata:
    """Build a table with a primary key on its first column."""
    key = columns[0].column_name
    keyed_columns = (columns[0].model_copy(update={"primary_key": True}), *columns[1:])
    return TableMetadata(
        schema_name=identifier(schema),
        table_name=identifier(name),
        columns=keyed_columns,
        primary_key=PrimaryKeyMetadata(constrained_columns=(key,)),
    )


def test_identifier_normalization_is_deterministic_for_both_dialects() -> None:
    postgres_unquoted = Identifier.from_raw("Orders", SchemaDialect.POSTGRESQL)
    postgres_quoted = Identifier.from_raw("Orders", SchemaDialect.POSTGRESQL, quoted=True)
    mysql_unquoted = Identifier.from_raw("Orders", SchemaDialect.MYSQL)
    mysql_quoted = Identifier.from_raw("Orders", SchemaDialect.MYSQL, quoted=True)

    assert postgres_unquoted.normalized_name == "orders"
    assert mysql_unquoted.normalized_name == "orders"
    assert postgres_quoted.normalized_name == "Orders"
    assert mysql_quoted.normalized_name == "Orders"


def test_default_namespaces_are_non_null_and_dialect_specific() -> None:
    assert default_schema_identifier(SchemaDialect.POSTGRESQL).normalized_name == "public"
    assert default_schema_identifier(SchemaDialect.MYSQL).normalized_name == "__default__"


def test_schema_serialization_is_versioned_and_deterministically_ordered() -> None:
    orders = table("sales", "orders", (column("id", 1),))
    users = table("public", "users", (column("name", 2), column("id", 1)))
    metadata = RawSchemaMetadata(
        dialect=DIALECT,
        schemas=(SchemaMetadata(schema_name=identifier("sales")), SchemaMetadata(schema_name=identifier("public"))),
        tables=(orders, users),
    )

    payload = metadata.model_dump(mode="json")

    assert payload["contract_version"] == "1.0"
    assert [item["schema_name"]["raw_name"] for item in payload["schemas"]] == ["public", "sales"]
    assert [item["table_name"]["raw_name"] for item in payload["tables"]] == ["users", "orders"]
    assert [item["column_name"]["raw_name"] for item in payload["tables"][0]["columns"]] == ["id", "name"]
    assert RawSchemaMetadata.model_validate_json(metadata.model_dump_json()) == metadata


def test_same_table_name_in_distinct_schemas_does_not_collide() -> None:
    metadata = RawSchemaMetadata(
        dialect=DIALECT,
        schemas=(SchemaMetadata(schema_name=identifier("sales")), SchemaMetadata(schema_name=identifier("audit"))),
        tables=(table("sales", "events", (column("id", 1),)), table("audit", "events", (column("id", 1),))),
    )

    assert len(metadata.tables) == 2
    assert metadata.tables[0].qualified_identity.canonical_key != metadata.tables[1].qualified_identity.canonical_key


def test_quoted_case_sensitive_table_and_unquoted_table_do_not_collide() -> None:
    quoted_table = table("public", "Orders", (column("id", 1),)).model_copy(
        update={"table_name": identifier("Orders", quoted=True)}
    )
    metadata = RawSchemaMetadata(
        dialect=DIALECT,
        schemas=(SchemaMetadata(schema_name=identifier("public")),),
        tables=(quoted_table, table("public", "orders", (column("id", 1),))),
    )

    assert [item.table_name.normalized_name for item in metadata.tables] == ["Orders", "orders"]


def test_duplicate_qualified_table_identity_is_rejected() -> None:
    duplicate_tables = (table("public", "Orders", (column("id", 1),)), table("public", "orders", (column("id", 1),)))

    with pytest.raises(ValidationError, match="Duplicate qualified table identity"):
        RawSchemaMetadata(
            dialect=DIALECT,
            schemas=(SchemaMetadata(schema_name=identifier("public")),),
            tables=duplicate_tables,
        )


def test_foreign_key_arity_mismatch_is_rejected() -> None:
    with pytest.raises(ValidationError, match="arity must match"):
        ForeignKeyMetadata(
            constrained_columns=(identifier("customer_id"), identifier("tenant_id")),
            referred_schema=identifier("public"),
            referred_table=identifier("customers"),
            referred_columns=(identifier("id"),),
        )


def test_raw_and_normalized_data_types_are_preserved() -> None:
    typed_column = ColumnMetadata(
        column_name=identifier("amount"),
        ordinal_position=1,
        raw_data_type="numeric(12, 2)",
        data_type="DECIMAL(12, 2)",
        nullable=False,
        default_expression="0.00",
    )

    assert typed_column.raw_data_type == "numeric(12, 2)"
    assert typed_column.data_type == "DECIMAL(12, 2)"
    assert typed_column.default_expression == "0.00"


def test_parse_diagnostics_are_separate_and_strictly_classify_completeness() -> None:
    empty_schema = RawSchemaMetadata(dialect=DIALECT)
    diagnostic = ParseDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=DiagnosticCode.NO_SUPPORTED_DDL,
        message="No supported table DDL was found",
        recoverable=False,
    )
    result = ParseResult(
        schema=empty_schema,
        diagnostics=(diagnostic,),
        completeness=ParseCompleteness.INCOMPLETE,
    )

    assert not hasattr(result.schema_metadata, "diagnostics")
    assert result.diagnostics == (diagnostic,)
    assert result.model_dump(mode="json", by_alias=True)["schema"]["contract_version"] == "1.0"


def test_complete_result_rejects_fatal_diagnostic() -> None:
    metadata = RawSchemaMetadata(
        dialect=DIALECT,
        schemas=(SchemaMetadata(schema_name=identifier("public")),),
        tables=(table("public", "users", (column("id", 1),)),),
    )
    diagnostic = ParseDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=DiagnosticCode.DDL_PARSE_ERROR,
        message="Supported DDL could not be parsed",
        recoverable=False,
    )

    with pytest.raises(ValidationError, match="cannot contain fatal diagnostics"):
        ParseResult(
            schema=metadata,
            diagnostics=(diagnostic,),
            completeness=ParseCompleteness.COMPLETE,
        )


def test_exact_foreign_key_mapping_is_represented_and_resolved() -> None:
    parent = table("core", "parents", (column("id", 1),))
    child_columns = (column("id", 1, primary_key=True), column("parent_id", 2))
    child = TableMetadata(
        schema_name=identifier("audit"),
        table_name=identifier("children"),
        columns=child_columns,
        primary_key=PrimaryKeyMetadata(constrained_columns=(identifier("id"),)),
        foreign_keys=(
            ForeignKeyMetadata(
                constrained_columns=(identifier("parent_id"),),
                referred_schema=identifier("core"),
                referred_table=identifier("parents"),
                referred_columns=(identifier("id"),),
            ),
        ),
    )

    metadata = RawSchemaMetadata(
        dialect=DIALECT,
        schemas=(SchemaMetadata(schema_name=identifier("audit")), SchemaMetadata(schema_name=identifier("core"))),
        tables=(child, parent),
    )

    assert metadata.tables[0].foreign_keys[0].referred_identity.canonical_key == ("core", "parents")
