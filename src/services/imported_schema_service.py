"""Persistence operations for user-owned imported schema metadata."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import ImportedSchemaModel
from src.models.schema_metadata import RawSchemaMetadata
from src.models.schemas import ImportedSchemaResponse, ImportedSchemaSummaryResponse


async def create_imported_schema(
    db: AsyncSession,
    owner_id: int,
    display_name: str,
    raw_schema: RawSchemaMetadata,
) -> ImportedSchemaResponse:
    """Persist validated schema metadata for one authenticated user."""
    record = ImportedSchemaModel(
        created_by=owner_id,
        display_name=display_name.strip(),
        dialect=raw_schema.dialect.value,
        schema_metadata=raw_schema.model_dump(mode="json"),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _full_response(record)


async def list_imported_schemas(
    db: AsyncSession,
    owner_id: int,
) -> list[ImportedSchemaSummaryResponse]:
    """List persisted schemas owned by one authenticated user."""
    statement = (
        select(ImportedSchemaModel)
        .where(ImportedSchemaModel.created_by == owner_id)
        .order_by(ImportedSchemaModel.updated_at.desc(), ImportedSchemaModel.id.desc())
    )
    records = (await db.scalars(statement)).all()
    return [_summary_response(record) for record in records]


async def get_imported_schema(
    db: AsyncSession,
    owner_id: int,
    schema_id: int,
) -> ImportedSchemaResponse | None:
    """Return one persisted schema only when it belongs to the user."""
    record = await _owned_record(db, owner_id, schema_id)
    return _full_response(record) if record else None


async def delete_imported_schema(db: AsyncSession, owner_id: int, schema_id: int) -> bool:
    """Delete one persisted schema only when it belongs to the user."""
    record = await _owned_record(db, owner_id, schema_id)
    if record is None:
        return False
    await db.delete(record)
    await db.commit()
    return True


async def _owned_record(
    db: AsyncSession,
    owner_id: int,
    schema_id: int,
) -> ImportedSchemaModel | None:
    statement = select(ImportedSchemaModel).where(
        ImportedSchemaModel.id == schema_id,
        ImportedSchemaModel.created_by == owner_id,
    )
    return await db.scalar(statement)


def _summary_response(record: ImportedSchemaModel) -> ImportedSchemaSummaryResponse:
    raw_schema = RawSchemaMetadata.model_validate(record.schema_metadata)
    return ImportedSchemaSummaryResponse(
        id=record.id,
        display_name=record.display_name,
        dialect=raw_schema.dialect,
        table_count=len(raw_schema.tables),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _full_response(record: ImportedSchemaModel) -> ImportedSchemaResponse:
    summary = _summary_response(record)
    raw_schema = RawSchemaMetadata.model_validate(record.schema_metadata)
    return ImportedSchemaResponse(**summary.model_dump(), raw_schema=raw_schema)
