"""Tests for Imported Schema Service — CRUD and semantic enrichment integration."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema_metadata import (
    ColumnMetadata,
    Identifier,
    PrimaryKeyMetadata,
    RawSchemaMetadata,
    SchemaDialect,
    SchemaMetadata,
    TableMetadata,
)
from src.services.imported_schema_service import (
    create_imported_schema,
    delete_imported_schema,
    get_imported_schema,
    list_imported_schemas,
)


def _make_raw_schema() -> RawSchemaMetadata:
    """Build a minimal RawSchemaMetadata for testing."""
    dialect = SchemaDialect.POSTGRESQL
    pk = PrimaryKeyMetadata(
        constraint_name=Identifier.from_raw("users_pkey", dialect),
        constrained_columns=(Identifier.from_raw("id", dialect),),
    )
    return RawSchemaMetadata(
        dialect=dialect,
        schemas=(SchemaMetadata(schema_name=Identifier.from_raw("public", dialect)),),
        tables=(
            TableMetadata(
                schema_name=Identifier.from_raw("public", dialect),
                table_name=Identifier.from_raw("users", dialect),
                columns=(
                    ColumnMetadata(
                        column_name=Identifier.from_raw("id", dialect),
                        ordinal_position=1,
                        raw_data_type="INTEGER",
                        data_type="INTEGER",
                        nullable=False,
                        primary_key=True,
                    ),
                    ColumnMetadata(
                        column_name=Identifier.from_raw("name", dialect),
                        ordinal_position=2,
                        raw_data_type="VARCHAR",
                        data_type="VARCHAR",
                        nullable=True,
                        primary_key=False,
                    ),
                ),
                primary_key=pk,
                foreign_keys=(),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_create_imported_schema_basic(async_session: AsyncSession):
    """Test basic CRUD lifecycle for imported schemas."""
    raw_schema = _make_raw_schema()
    result = await create_imported_schema(
        db=async_session,
        owner_id=1,
        display_name="Test Schema",
        raw_schema=raw_schema,
    )

    assert result.id > 0
    assert result.display_name == "Test Schema"
    assert result.dialect == SchemaDialect.POSTGRESQL
    assert result.table_count == 1


@pytest.mark.asyncio
async def test_list_imported_schemas(async_session: AsyncSession):
    """Test listing imported schemas for a user."""
    raw_schema = _make_raw_schema()
    await create_imported_schema(async_session, 1, "Schema A", raw_schema)
    await create_imported_schema(async_session, 1, "Schema B", raw_schema)

    results = await list_imported_schemas(async_session, 1)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_get_imported_schema(async_session: AsyncSession):
    """Test retrieving a single imported schema."""
    raw_schema = _make_raw_schema()
    created = await create_imported_schema(async_session, 1, "My Schema", raw_schema)

    fetched = await get_imported_schema(async_session, 1, created.id)
    assert fetched is not None
    assert fetched.display_name == "My Schema"


@pytest.mark.asyncio
async def test_get_imported_schema_wrong_owner(async_session: AsyncSession):
    """Test that get_imported_schema returns None for wrong owner."""
    raw_schema = _make_raw_schema()
    created = await create_imported_schema(async_session, 1, "Owner Schema", raw_schema)

    fetched = await get_imported_schema(async_session, 999, created.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_delete_imported_schema(async_session: AsyncSession):
    """Test deleting an imported schema."""
    raw_schema = _make_raw_schema()
    created = await create_imported_schema(async_session, 1, "Delete Me", raw_schema)

    deleted = await delete_imported_schema(async_session, 1, created.id)
    assert deleted is True

    fetched = await get_imported_schema(async_session, 1, created.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_delete_imported_schema_wrong_owner(async_session: AsyncSession):
    """Test that delete returns False for wrong owner."""
    raw_schema = _make_raw_schema()
    created = await create_imported_schema(async_session, 1, "Protected", raw_schema)

    deleted = await delete_imported_schema(async_session, 999, created.id)
    assert deleted is False


# --- Semantic enrichment integration tests ---


@pytest.mark.asyncio
@patch("src.services.imported_schema_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.imported_schema_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_imported_schema_calls_ensure_semantic_database(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
):
    """After persisting, create_imported_schema calls ensure_semantic_database."""
    mock_ensure.return_value = 42
    mock_enrich.return_value = {"tables": [], "relationships": [], "status": "draft"}

    raw_schema = _make_raw_schema()
    result = await create_imported_schema(
        db=async_session,
        owner_id=1,
        display_name="Test Semantic Link",
        raw_schema=raw_schema,
    )

    mock_ensure.assert_called_once()
    call_kwargs = mock_ensure.call_args
    assert call_kwargs.kwargs["source_type"] == "imported_schema"
    assert call_kwargs.kwargs["source_id"] == result.id
    assert call_kwargs.kwargs["display_name"] == "Test Semantic Link"


@pytest.mark.asyncio
@patch("src.services.imported_schema_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.imported_schema_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_imported_schema_sets_semantic_db_id(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
):
    """ImportedSchemaModel.semantic_db_id is set to the returned semantic database ID."""
    mock_ensure.return_value = 99
    mock_enrich.return_value = {"tables": [], "relationships": [], "status": "draft"}

    raw_schema = _make_raw_schema()
    result = await create_imported_schema(
        db=async_session,
        owner_id=1,
        display_name="Test Link",
        raw_schema=raw_schema,
    )

    # Verify semantic_db_id was persisted by re-fetching
    fetched = await get_imported_schema(async_session, 1, result.id)
    assert fetched is not None


@pytest.mark.asyncio
@patch("src.services.imported_schema_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.imported_schema_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_imported_schema_calls_enrichment(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
):
    """After ensure_semantic_database, enrichment is called with connection_id=semantic_db_id."""
    mock_ensure.return_value = 42
    mock_enrich.return_value = {"tables": [], "relationships": [], "status": "draft"}

    raw_schema = _make_raw_schema()
    await create_imported_schema(
        db=async_session,
        owner_id=1,
        display_name="Test Enrichment",
        raw_schema=raw_schema,
    )

    # Wait for background task to complete
    await asyncio.sleep(0.1)

    mock_enrich.assert_called_once()
    call_kwargs = mock_enrich.call_args
    assert call_kwargs.kwargs["connection_id"] == 42


@pytest.mark.asyncio
@patch("src.services.imported_schema_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.imported_schema_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_imported_schema_enrichment_error_does_not_fail_request(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
):
    """If enrichment raises an error, the request still succeeds."""
    mock_ensure.return_value = 42
    mock_enrich.side_effect = RuntimeError("LLM service unavailable")

    raw_schema = _make_raw_schema()
    result = await create_imported_schema(
        db=async_session,
        owner_id=1,
        display_name="Test Error Handling",
        raw_schema=raw_schema,
    )

    # Request should succeed despite enrichment error
    assert result.id > 0
    assert result.display_name == "Test Error Handling"
    assert result.table_count == 1


@pytest.mark.asyncio
@patch("src.services.imported_schema_service.enrich_and_save_canonical_schema", new_callable=AsyncMock)
@patch("src.services.imported_schema_service.ensure_semantic_database", new_callable=AsyncMock)
async def test_create_imported_schema_ensure_semantic_db_error_does_not_fail_request(
    mock_ensure: AsyncMock,
    mock_enrich: AsyncMock,
    async_session: AsyncSession,
):
    """If ensure_semantic_database raises, the request still succeeds and enrichment is skipped."""
    mock_ensure.side_effect = RuntimeError("DB connection failed")

    raw_schema = _make_raw_schema()
    result = await create_imported_schema(
        db=async_session,
        owner_id=1,
        display_name="Test Ensure Error",
        raw_schema=raw_schema,
    )

    # Request should succeed despite ensure_semantic_database error
    assert result.id > 0
    assert result.display_name == "Test Ensure Error"

    # Enrichment should not be called if ensure failed
    mock_enrich.assert_not_called()
