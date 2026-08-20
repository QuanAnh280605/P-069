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
from sqlalchemy.orm import selectinload

from src.models.db import (
    CanonicalRelationshipModel,
    MetricVersionModel,
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
    """Fetch all enriched tables with their columns eagerly loaded."""
    result = await db.execute(
        select(SemanticTableModel)
        .where(SemanticTableModel.db_id == db_id)
        .options(selectinload(SemanticTableModel.columns))
    )
    return list(result.scalars().all())


async def _load_metrics(db: AsyncSession, db_id: int) -> list[SemanticMetricModel]:
    """Fetch all metrics for a given database, eagerly loading versions."""
    result = await db.execute(
        select(SemanticMetricModel)
        .where(SemanticMetricModel.db_id == db_id)
        .options(selectinload(SemanticMetricModel.versions))
    )
    return list(result.scalars().all())


async def _load_relationships(db: AsyncSession, db_id: int) -> list[CanonicalRelationshipModel]:
    """Fetch all canonical relationships for a given database."""
    result = await db.execute(
        select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == db_id)
    )
    return list(result.scalars().all())


async def _load_metric_versions(db: AsyncSession, db_id: int) -> list[MetricVersionModel]:
    """Fetch all metric versions for metrics belonging to a given database."""
    result = await db.execute(
        select(MetricVersionModel)
        .join(SemanticMetricModel, MetricVersionModel.metric_id == SemanticMetricModel.id)
        .where(SemanticMetricModel.db_id == db_id)
    )
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


def _dimension_to_dict(col: SemanticColumnModel) -> dict[str, Any]:
    """Convert a column model to a canonical dimension dictionary."""
    return {
        "column_name": col.column_name,
        "table_id": col.table_id,
        "data_type": col.data_type,
        "business_name": col.business_name,
        "description": col.description,
        "is_primary_key": col.is_primary_key,
        "is_foreign_key": col.is_foreign_key,
        "is_nullable": col.is_nullable,
        "is_time_dimension": col.is_time_dimension,
        "allowed_values": col.allowed_values,
    }


def _metric_to_dict(met: SemanticMetricModel) -> dict[str, Any]:
    """Convert a metric model to a canonical metric dictionary with version info."""
    versions = [
        {
            "id": v.id,
            "version": v.version,
            "formula": v.formula,
            "definition": v.definition,
            "changed_by": v.changed_by,
            "change_reason": v.change_reason,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in sorted(met.versions, key=lambda v: v.version)
    ]
    return {
        "id": met.id,
        "name": met.name,
        "description": met.description,
        "sql_template": met.sql_template,
        "source": met.source,
        "formula": met.formula,
        "definition": met.definition,
        "aggregation_type": met.aggregation_type,
        "version": met.version,
        "status": met.status,
        "approved_by": met.approved_by,
        "base_entity_id": met.base_entity_id,
        "created_by": met.created_by,
        "versions": versions,
    }


def _relationship_to_dict(rel: CanonicalRelationshipModel) -> dict[str, Any]:
    """Convert a canonical relationship model to a plain dictionary."""
    return {
        "id": rel.id,
        "connection_id": rel.connection_id,
        "from_entity_id": rel.from_entity_id,
        "to_entity_id": rel.to_entity_id,
        "relationship_type": rel.relationship_type,
        "join_condition": rel.join_condition,
        "created_at": rel.created_at.isoformat() if rel.created_at else None,
    }


def _metric_version_to_dict(ver: MetricVersionModel) -> dict[str, Any]:
    """Convert a metric version model to a plain dictionary."""
    return {
        "id": ver.id,
        "metric_id": ver.metric_id,
        "version": ver.version,
        "formula": ver.formula,
        "definition": ver.definition,
        "changed_by": ver.changed_by,
        "change_reason": ver.change_reason,
        "created_at": ver.created_at.isoformat() if ver.created_at else None,
    }


async def build_semantic_layer_dict(db: AsyncSession, db_id: int) -> dict[str, Any]:
    """Assemble the full Semantic Layer as a nested dictionary.

    Returns a dict with 6 top-level keys:
      - database: metadata (no conn_url_enc)
      - canonical_entities: tables with physical_schema, primary_key_column
      - canonical_relationships: FK/join relationships
      - canonical_dimensions: all columns with is_time_dimension, allowed_values
      - canonical_metrics: metrics with formula, aggregation_type, version, status, versions
      - metric_versions: flat list of all metric version records

    Raises ValueError if the database record is not found.
    """
    database = await _load_database(db, db_id)
    if not database:
        raise ValueError(f"SemanticDatabase with id={db_id} not found")

    tables = await _load_tables(db, db_id)
    metrics = await _load_metrics(db, db_id)
    relationships = await _load_relationships(db, db_id)
    metric_versions = await _load_metric_versions(db, db_id)

    # Build canonical_entities (tables with nested columns)
    entity_list: list[dict[str, Any]] = []
    all_columns: list[SemanticColumnModel] = []
    for table in tables:
        columns = sorted(table.columns, key=lambda col: col.id)
        all_columns.extend(columns)
        entity_list.append(
            {
                "table_name": table.table_name,
                "business_name": table.business_name,
                "description": table.description,
                "physical_schema": table.physical_schema,
                "primary_key_column": table.primary_key_column,
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
        "canonical_entities": entity_list,
        "canonical_relationships": [_relationship_to_dict(r) for r in relationships],
        "canonical_dimensions": [_dimension_to_dict(c) for c in all_columns],
        "canonical_metrics": [_metric_to_dict(m) for m in metrics],
        "metric_versions": [_metric_version_to_dict(v) for v in metric_versions],
    }


def serialize_to_json(data: dict[str, Any]) -> str:
    """Serialize Semantic Layer dict to formatted JSON string."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def serialize_to_yaml(data: dict[str, Any]) -> str:
    """Serialize Semantic Layer dict to YAML string."""
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
