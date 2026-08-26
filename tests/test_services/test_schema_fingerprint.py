"""Unit tests for schema fingerprint computation and fast inspection."""

import sqlite3

from src.models.schema_metadata import (
    ColumnMetadata,
    Identifier,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
)
from src.services.schema_fingerprint import (
    compute_schema_fingerprint,
    fast_introspect_schema_fingerprint,
)


def _build_test_raw_schema(col_name: str = "amount") -> RawSchemaMetadata:
    """Build canonical raw schema for testing."""
    dialect = SchemaDialect.SQLITE
    schema_id = Identifier.from_raw("main", dialect)
    table_id = Identifier.from_raw("orders", dialect)
    col_id = Identifier.from_raw(col_name, dialect)

    column = ColumnMetadata(
        column_name=col_id,
        ordinal_position=1,
        raw_data_type="INTEGER",
        data_type="INTEGER",
        nullable=False,
        primary_key=True,
    )
    table = TableMetadata(
        schema_name=schema_id,
        table_name=table_id,
        columns=(column,),
        primary_key=PrimaryKeyMetadata(constrained_columns=(col_id,)),
    )
    return RawSchemaMetadata(
        dialect=dialect,
        schemas=(SchemaMetadata(schema_name=schema_id),),
        tables=(table,),
    )


def test_compute_schema_fingerprint_deterministic():
    """Verify that identical schema generates the exact same hash."""
    schema1 = _build_test_raw_schema("amount")
    schema2 = _build_test_raw_schema("amount")
    schema3 = _build_test_raw_schema("total_price")

    fp1 = compute_schema_fingerprint(schema1)
    fp2 = compute_schema_fingerprint(schema2)
    fp3 = compute_schema_fingerprint(schema3)

    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 32


def test_fast_introspect_schema_fingerprint(tmp_path):
    """Test fast inspection on a real sqlite database."""
    db_file = tmp_path / "test_target.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, title TEXT, price REAL)")
    conn.commit()
    conn.close()

    conn_url = f"sqlite:///{db_file}"
    fp = fast_introspect_schema_fingerprint(conn_url, "sqlite")
    assert isinstance(fp, str)
    assert len(fp) == 32
