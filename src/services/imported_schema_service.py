"""Persistence operations for user-owned imported schema metadata."""

import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import ImportedSchemaModel, SemanticDatabaseModel
from src.models.schema_metadata import RawSchemaMetadata
from src.models.schemas import ImportedSchemaResponse, ImportedSchemaSummaryResponse
from src.services.database import get_db_session
from src.services.live_db_service import _safe_raw_schema
from src.services.semantic_service import enrich_and_save_canonical_schema, ensure_semantic_database

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()


async def create_imported_schema(
    db: AsyncSession,
    owner_id: int,
    display_name: str,
    raw_schema: RawSchemaMetadata,
    org_id: int | None = None,
) -> ImportedSchemaResponse:
    """Persist validated schema metadata for one authenticated user."""
    logger.info(
        "Saving imported schema '%s' (%d tables, dialect=%s)...",
        display_name,
        len(raw_schema.tables),
        raw_schema.dialect.value,
    )
    record = ImportedSchemaModel(
        created_by=owner_id,
        display_name=display_name.strip(),
        dialect=raw_schema.dialect.value,
        schema_metadata=raw_schema.model_dump(mode="json"),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    logger.info("Saved ImportedSchemaModel record ID=%d for '%s'", record.id, display_name)

    try:
        semantic_db_id = await ensure_semantic_database(
            db=db,
            source_type="imported_schema",
            source_id=record.id,
            user_id=owner_id,
            display_name=display_name.strip(),
            dialect=raw_schema.dialect.value,
            org_id=org_id,
        )
        record.semantic_db_id = semantic_db_id
        await db.commit()
        await db.refresh(record)

        logger.info(
            "Created SemanticDatabaseModel ID=%d for imported schema %d. Dispatching background AI enrichment task...",
            semantic_db_id,
            record.id,
        )
        task = asyncio.create_task(
            _run_enrichment_background(
                user_id=owner_id,
                connection_id=semantic_db_id,
                raw_schema=raw_schema,
                dialect=raw_schema.dialect.value,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except Exception:
        logger.warning("Failed to create semantic database for imported schema %d", record.id, exc_info=True)

    return _full_response(record)


async def list_imported_schemas(
    db: AsyncSession,
    owner_id: int,
    org_id: int | None = None,
) -> list[ImportedSchemaSummaryResponse]:
    """List persisted schemas owned by one authenticated user."""
    statement = select(ImportedSchemaModel).order_by(
        ImportedSchemaModel.updated_at.desc(), ImportedSchemaModel.id.desc()
    )
    if org_id is None:
        statement = statement.where(ImportedSchemaModel.created_by == owner_id)
    else:
        statement = statement.outerjoin(
            SemanticDatabaseModel, ImportedSchemaModel.semantic_db_id == SemanticDatabaseModel.id
        ).where(
            (SemanticDatabaseModel.org_id == org_id)
            | ((SemanticDatabaseModel.org_id.is_(None)) & (ImportedSchemaModel.created_by == owner_id))
        )
    records = (await db.scalars(statement)).all()
    return [_summary_response(record) for record in records]


async def get_imported_schema(
    db: AsyncSession,
    owner_id: int,
    schema_id: int,
    org_id: int | None = None,
) -> ImportedSchemaResponse | None:
    """Return one persisted schema only when it belongs to the user."""
    record = await _owned_record(db, owner_id, schema_id, org_id)
    return _full_response(record) if record else None


async def delete_imported_schema(db: AsyncSession, owner_id: int, schema_id: int, org_id: int | None = None) -> bool:
    """Delete one persisted schema and all related semantic layer metadata when it belongs to the user."""
    record = await _owned_record(db, owner_id, schema_id, org_id)
    if record is None:
        return False

    sem_db_id = record.semantic_db_id
    await db.delete(record)

    if sem_db_id:
        sem_db = await db.get(SemanticDatabaseModel, sem_db_id)
        if sem_db:
            await db.delete(sem_db)
    else:
        conn_key = f"semantic:import:{schema_id}"
        sem_stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.conn_url_enc == conn_key)
        sem_db = (await db.execute(sem_stmt)).scalar_one_or_none()
        if sem_db:
            await db.delete(sem_db)

    await db.commit()
    return True


async def _owned_record(
    db: AsyncSession,
    owner_id: int,
    schema_id: int,
    org_id: int | None = None,
) -> ImportedSchemaModel | None:
    statement = select(ImportedSchemaModel).where(ImportedSchemaModel.id == schema_id)
    if org_id is None:
        statement = statement.where(ImportedSchemaModel.created_by == owner_id)
    else:
        statement = statement.outerjoin(
            SemanticDatabaseModel, ImportedSchemaModel.semantic_db_id == SemanticDatabaseModel.id
        ).where(
            (SemanticDatabaseModel.org_id == org_id)
            | ((SemanticDatabaseModel.org_id.is_(None)) & (ImportedSchemaModel.created_by == owner_id))
        )
    return await db.scalar(statement)


def _summary_response(record: ImportedSchemaModel) -> ImportedSchemaSummaryResponse:
    raw_schema = _safe_raw_schema(record.schema_metadata, record.dialect)
    return ImportedSchemaSummaryResponse(
        id=record.id,
        semantic_db_id=record.semantic_db_id,
        display_name=record.display_name,
        dialect=raw_schema.dialect,
        table_count=len(raw_schema.tables),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _full_response(record: ImportedSchemaModel) -> ImportedSchemaResponse:
    summary = _summary_response(record)
    raw_schema = _safe_raw_schema(record.schema_metadata, record.dialect)
    return ImportedSchemaResponse(**summary.model_dump(), raw_schema=raw_schema)


async def _run_enrichment_background(
    user_id: int,
    connection_id: int,
    raw_schema: RawSchemaMetadata,
    dialect: str,
) -> None:
    """Run schema enrichment in background with its own DB session."""
    logger.info(
        "Starting background AI semantic enrichment for imported schema connection_id=%d (%d tables)...",
        connection_id,
        len(raw_schema.tables),
    )
    try:
        async for session in get_db_session():
            await enrich_and_save_canonical_schema(
                db=session,
                user_id=user_id,
                connection_id=connection_id,
                raw_schema=raw_schema,
                dialect=dialect,
            )
            await session.commit()
            logger.info("Successfully completed AI semantic enrichment for connection_id=%d", connection_id)
    except Exception as exc:
        logger.warning("Background enrichment failed for connection_id=%d: %s", connection_id, exc, exc_info=True)
