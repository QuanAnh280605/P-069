"""Unit tests for MySQL Live Target Database connection, metadata serialization, and Fernet encryption."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema_metadata import SchemaDialect
from src.services.live_db_service import create_live_target_db, introspect_live_database


def _mock_mysql_inspector() -> MagicMock:
    """Build a mock SQLAlchemy Inspector simulating a MySQL database."""
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["users", "orders"]
    inspector.get_columns.side_effect = lambda table_name: [
        {"name": f"{table_name[:-1]}_id", "type": "INT", "nullable": False, "default": None},
        {"name": "name", "type": "VARCHAR(255)", "nullable": True, "default": None},
    ]
    inspector.get_pk_constraint.side_effect = lambda table_name: {"constrained_columns": [f"{table_name[:-1]}_id"]}
    inspector.get_foreign_keys.return_value = []
    return inspector


@patch("src.services.live_db_service.inspect")
@patch("src.services.live_db_service.create_engine")
def test_mysql_introspect_live_database(mock_create_engine: MagicMock, mock_inspect: MagicMock) -> None:
    """Test MySQL zero-data schema introspection logic with mocked engine."""
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_inspect.return_value = _mock_mysql_inspector()

    conn_url = "mysql+pymysql://root:devpassword@localhost:3306/ecommerce_db"
    schema = introspect_live_database(conn_url, SchemaDialect.MYSQL)

    assert schema.dialect == SchemaDialect.MYSQL
    assert schema.tables is not None
    table_names = [table.table_name.raw_name for table in schema.tables]
    assert "users" in table_names
    assert "orders" in table_names

    users_table = next(t for t in schema.tables if t.table_name.raw_name == "users")
    col_names = [c.column_name.raw_name for c in users_table.columns]
    assert "user_id" in col_names
    assert "name" in col_names
    mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.live_db_service.introspect_live_database")
async def test_create_mysql_live_target_db(
    mock_introspect: MagicMock,
    async_session: AsyncSession,
) -> None:
    """Test creating and persisting a MySQL Live Target DB record."""
    from src.models.schema_metadata import (
        ColumnMetadata,
        Identifier,
        PrimaryKeyMetadata,
        RawSchemaMetadata,
        SchemaMetadata,
        TableMetadata,
    )

    schema_meta = SchemaMetadata(schema_name=Identifier.from_raw("__default__", SchemaDialect.MYSQL))
    table_meta = TableMetadata(
        schema_name=Identifier.from_raw("__default__", SchemaDialect.MYSQL),
        table_name=Identifier.from_raw("products", SchemaDialect.MYSQL),
        columns=(
            ColumnMetadata(
                column_name=Identifier.from_raw("id", SchemaDialect.MYSQL),
                ordinal_position=1,
                raw_data_type="INT",
                data_type="INT",
                nullable=False,
                primary_key=True,
            ),
        ),
        primary_key=PrimaryKeyMetadata(
            constrained_columns=(Identifier.from_raw("id", SchemaDialect.MYSQL),),
        ),
    )
    mock_introspect.return_value = RawSchemaMetadata(
        dialect=SchemaDialect.MYSQL,
        schemas=(schema_meta,),
        tables=(table_meta,),
    )

    conn_url = "mysql+pymysql://root:devpassword@localhost:3306/ecommerce_db"
    created = await create_live_target_db(
        db=async_session,
        user_id=1,
        display_name="MySQL Test DB",
        dialect=SchemaDialect.MYSQL,
        conn_url=conn_url,
    )

    assert created.id > 0
    assert created.display_name == "MySQL Test DB"
    assert created.dialect == SchemaDialect.MYSQL
    assert created.table_count == 1
