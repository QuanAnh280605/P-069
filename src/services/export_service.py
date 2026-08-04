"""Export Service — Serialize approved Semantic Layer to JSON or YAML.

Reads enriched data from Metadata Store and assembles a portable
Semantic Layer document for BI tool integration (Metabase, dbt, Looker).
"""

from __future__ import annotations

import json
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import (
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)


async def _load_database(db: AsyncSession, db_id: int) -> SemanticDatabaseModel | None:
    """Fetch SemanticDatabaseModel by ID."""
    result = await db.execute(select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == db_id))
    return result.scalar_one_or_none()


async def _load_tables(db: AsyncSession, db_id: int) -> list[SemanticTableModel]:
    """Fetch all enriched tables for a given database."""
    result = await db.execute(select(SemanticTableModel).where(SemanticTableModel.db_id == db_id))
    return list(result.scalars().all())


async def _load_columns(db: AsyncSession, table_id: int) -> list[SemanticColumnModel]:
    """Fetch all enriched columns for a given table."""
    result = await db.execute(select(SemanticColumnModel).where(SemanticColumnModel.table_id == table_id))
    return list(result.scalars().all())


async def _load_metrics(db: AsyncSession, db_id: int) -> list[SemanticMetricModel]:
    """Fetch all approved metrics for a given database."""
    result = await db.execute(select(SemanticMetricModel).where(SemanticMetricModel.db_id == db_id))
    return list(result.scalars().all())


def _column_to_dict(col: SemanticColumnModel) -> dict[str, Any]:
    """Convert a column model to a plain dictionary."""
    return {
        "column_name": col.column_name,
        "data_type": col.data_type,
        "business_name": col.business_name,
        "description": col.description,
        "is_primary_key": col.is_primary_key,
        "is_foreign_key": col.is_foreign_key,
        "fk_target_table": col.fk_target_table,
        "fk_target_column": col.fk_target_column,
        "is_nullable": col.is_nullable,
    }


def _metric_to_dict(met: SemanticMetricModel) -> dict[str, Any]:
    """Convert a metric model to a plain dictionary."""
    return {
        "id": met.id,
        "name": met.name,
        "description": met.description,
        "sql_template": met.sql_template,
        "source": met.source,
    }


async def build_semantic_layer_dict(db: AsyncSession, db_id: int) -> dict[str, Any]:
    """Assemble the full Semantic Layer as a nested dictionary.

    Returns a dict with keys: database, tables (with columns), metrics.
    Raises ValueError if the database record is not found.
    """
    database = await _load_database(db, db_id)
    if not database:
        raise ValueError(f"SemanticDatabase with id={db_id} not found")

    tables = await _load_tables(db, db_id)
    metrics = await _load_metrics(db, db_id)

    table_list: list[dict[str, Any]] = []
    for table in tables:
        columns = await _load_columns(db, table.id)
        table_list.append(
            {
                "table_name": table.table_name,
                "business_name": table.business_name,
                "description": table.description,
                "columns": [_column_to_dict(c) for c in columns],
            }
        )

    return {
        "database": {
            "id": database.id,
            "display_name": database.display_name,
            "db_type": database.db_type,
            "status": database.status,
        },
        "tables": table_list,
        "metrics": [_metric_to_dict(m) for m in metrics],
    }


def serialize_to_json(data: dict[str, Any]) -> str:
    """Serialize Semantic Layer dict to formatted JSON string."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def serialize_to_yaml(data: dict[str, Any]) -> str:
    """Serialize Semantic Layer dict to YAML string."""
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
