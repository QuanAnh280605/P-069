"""Validation and persistence projections for canonical metric definitions."""

from __future__ import annotations

import sqlglot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from src.models.db import (
    ImportedSchemaModel,
    LiveTargetDbModel,
    SemanticColumnModel,
    SemanticTableModel,
)
from src.models.metric_definition import MetricDefinition, MetricStatus
from src.models.schema_metadata import RawSchemaMetadata

_NUMERIC_TYPES = (
    "INT",
    "DECIMAL",
    "NUMERIC",
    "FLOAT",
    "DOUBLE",
    "REAL",
    "MONEY",
    "NUMBER",
    "SERIAL",
    "TINYINT",
    "BIGINT",
    "SMALLINT",
)


async def validate_metric_definition(
    db: AsyncSession,
    db_id: int,
    definition: MetricDefinition,
) -> SemanticTableModel:
    """Validate entity and fields against persisted semantic metadata."""
    table = await _load_base_entity(db, db_id, definition.metric.base_entity)
    definition.metric.base_entity = table.table_name
    columns = await _load_columns(db, table.id)
    column_map = {column.column_name: column for column in columns}
    _validate_expression_columns(definition, column_map)
    _validate_filter_columns(definition, column_map)
    return table


def with_metric_status(definition: MetricDefinition, status: MetricStatus) -> MetricDefinition:
    """Return a copied definition with the authoritative lifecycle status."""
    return definition.model_copy(update={"metric": definition.metric.model_copy(update={"status": status})})


async def _load_base_entity(db: AsyncSession, db_id: int, base_entity: str) -> SemanticTableModel:
    stmt = select(SemanticTableModel).where(SemanticTableModel.db_id == db_id)
    tables = (await db.execute(stmt)).scalars().all()
    clean_target = base_entity.strip().lower()
    for tbl in tables:
        if tbl.table_name.strip().lower() == clean_target:
            return tbl

    # Auto-bootstrap if semantic_tables has no records for db_id
    if not tables:
        await _bootstrap_semantic_tables_if_empty(db, db_id)
        stmt = select(SemanticTableModel).where(SemanticTableModel.db_id == db_id)
        tables = (await db.execute(stmt)).scalars().all()
        for tbl in tables:
            if tbl.table_name.strip().lower() == clean_target:
                return tbl

    raise ValueError(f"Unknown base_entity: {base_entity}")


async def _bootstrap_semantic_tables_if_empty(db: AsyncSession, db_id: int) -> None:
    """Bootstrap draft semantic tables and columns from source raw_schema if missing."""
    live_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == db_id)
    live_db = (await db.execute(live_stmt)).scalar_one_or_none()
    raw_schema_dict = None
    user_id = 1
    if live_db:
        raw_schema_dict = live_db.schema_metadata
        user_id = live_db.created_by or 1
    else:
        imported_stmt = select(ImportedSchemaModel).where(ImportedSchemaModel.semantic_db_id == db_id)
        imported = (await db.execute(imported_stmt)).scalar_one_or_none()
        if imported:
            raw_schema_dict = imported.schema_metadata
            user_id = imported.created_by or 1

    if not raw_schema_dict:
        return

    raw_meta = RawSchemaMetadata.model_validate(raw_schema_dict)
    for table_meta in raw_meta.tables:
        t_name = table_meta.table_name.raw_name
        pk_cols = table_meta.primary_key.constrained_columns if table_meta.primary_key else ()
        pk_col_name = pk_cols[0].raw_name if pk_cols else None
        tbl_record = SemanticTableModel(
            db_id=db_id,
            table_name=t_name,
            business_name=t_name.replace("_", " ").title(),
            description="",
            physical_schema=table_meta.schema_name.raw_name,
            primary_key_column=pk_col_name,
            created_by=user_id,
        )
        db.add(tbl_record)
        await db.flush()
        for col_meta in table_meta.columns:
            c_name = col_meta.column_name.raw_name
            is_time = col_meta.data_type.upper().strip() in {"TIMESTAMP", "DATE", "DATETIME"}
            col_record = SemanticColumnModel(
                table_id=tbl_record.id,
                column_name=c_name,
                data_type=col_meta.data_type,
                business_name=c_name.replace("_", " ").title(),
                description="",
                is_primary_key=col_meta.primary_key,
                is_nullable=col_meta.nullable,
                is_time_dimension=is_time,
            )
            db.add(col_record)
    await db.flush()


async def _load_columns(db: AsyncSession, table_id: int) -> list[SemanticColumnModel]:
    result = await db.execute(select(SemanticColumnModel).where(SemanticColumnModel.table_id == table_id))
    return list(result.scalars().all())


def _validate_expression_columns(
    definition: MetricDefinition,
    columns: dict[str, SemanticColumnModel],
) -> None:
    formula = definition.metric.formula
    if formula.expression == "*":
        return
    parsed = sqlglot.parse_one(formula.expression)
    col_map_lower = {k.lower(): (k, v) for k, v in columns.items()}
    names = {column.name.lower() for column in parsed.find_all(exp.Column)}
    missing = names - col_map_lower.keys()
    if missing:
        raise ValueError(f"Unknown expression columns: {sorted(missing)}")
    if formula.function in {"SUM", "AVG"}:
        invalid = [col_map_lower[name][0] for name in names if not _is_numeric(col_map_lower[name][1].data_type)]
        if invalid:
            raise ValueError(f"{formula.function} requires numeric columns: {invalid}")


def _validate_filter_columns(
    definition: MetricDefinition,
    columns: dict[str, SemanticColumnModel],
) -> None:
    col_map_lower = {k.lower(): k for k in columns.keys()}
    missing = {item.field.lower() for item in definition.metric.filters} - col_map_lower.keys()
    if missing:
        raise ValueError(f"Unknown filter columns: {sorted(missing)}")


def _is_numeric(data_type: str) -> bool:
    return any(token in data_type.upper() for token in _NUMERIC_TYPES)
