"""Semantic Service — Canonical schema enrichment, metric CRUD, and HITL compliance.

Provides:
  - ensure_semantic_database: Create or find SemanticDatabaseModel for a source.
  - enrich_and_save_canonical_schema: LLM-enrich raw schema → draft semantic tables/columns/FKs.
  - create_metric / update_metric / approve_metric: Metric lifecycle with versioning.
  - get_metric_with_history: Metric retrieval with version history.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import (
    CanonicalRelationshipModel,
    ImportedSchemaModel,
    LiveTargetDbModel,
    MetricVersionModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.models.metric_definition import MetricDefinition
from src.models.schema_metadata import RawSchemaMetadata
from src.services.llm import get_llm
from src.services.metric_definitions import validate_metric_definition, with_metric_status

logger = logging.getLogger(__name__)

_TIME_DIMENSION_TYPES = {"TIMESTAMP", "TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP WITH TIME ZONE", "DATE", "DATETIME"}


async def ensure_semantic_database(
    db: AsyncSession,
    source_type: str,
    source_id: int,
    user_id: int,
    display_name: str,
    dialect: str,
) -> int:
    """Create or retrieve a SemanticDatabaseModel for a given source.

    Uses a deterministic conn_url_enc key to deduplicate: ``semantic:{source_type}:{source_id}``.
    Returns the semantic_databases.id.
    """
    conn_key = f"semantic:{source_type}:{source_id}"
    stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.conn_url_enc == conn_key)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing.id

    record = SemanticDatabaseModel(
        created_by=user_id,
        display_name=display_name,
        db_type=dialect,
        conn_url_enc=conn_key,
        status="draft",
    )
    db.add(record)
    await db.flush()
    return record.id


async def enrich_and_save_canonical_schema(
    db: AsyncSession,
    user_id: int,
    connection_id: int,
    raw_schema: RawSchemaMetadata,
    dialect: str,
) -> dict[str, Any]:
    """Enrich raw schema metadata with LLM-generated business names and save as draft.

    Steps:
      1. Build LLM prompt from raw schema tables/columns.
      2. Call LLM for Vietnamese business names and descriptions.
      3. Upsert into semantic_tables and semantic_columns (status implicit via model defaults).
      4. Extract foreign keys into canonical_relationships.
      5. Return summary dict with status='draft'.
    """
    logger.info(
        "[AI Semantic Agent] Starting canonical schema enrichment for connection_id=%d (%d tables)...",
        connection_id,
        len(raw_schema.tables),
    )
    enrichment = await _call_llm_enrichment(raw_schema, dialect)
    logger.info("[AI Semantic Agent] LLM enrichment returned data for %d tables", len(enrichment))
    table_id_map: dict[str, int] = {}

    for table_meta in raw_schema.tables:
        table_name = table_meta.table_name.raw_name
        table_enrichment = enrichment.get(table_name, {})
        pk_cols = table_meta.primary_key.constrained_columns if table_meta.primary_key else ()
        pk_col_name = pk_cols[0].raw_name if pk_cols else None

        table_id = await _upsert_semantic_table(
            db=db,
            connection_id=connection_id,
            table_name=table_name,
            enrichment=table_enrichment,
            schema_name=table_meta.schema_name.raw_name,
            pk_col=pk_col_name,
            user_id=user_id,
        )
        table_id_map[table_name] = table_id
        bname = table_enrichment.get("business_name", table_name)
        logger.info(
            "[AI Semantic Agent] Processed table '%s' (ID=%d, business_name='%s', columns=%d)",
            table_name,
            table_id,
            bname,
            len(table_meta.columns),
        )

        col_enrichments = {c["column_name"]: c for c in table_enrichment.get("columns", [])}
        for col_meta in table_meta.columns:
            col_enrich = col_enrichments.get(col_meta.column_name.raw_name, {})
            await _upsert_semantic_column(
                db=db,
                table_id=table_id,
                col_meta=col_meta,
                enrichment=col_enrich,
            )

    relationships = await _extract_and_save_relationships(db, connection_id, raw_schema, table_id_map)
    logger.info(
        "[AI Semantic Agent] Extracted %d foreign key relationships for connection_id=%d",
        len(relationships),
        connection_id,
    )

    await db.commit()
    logger.info("[AI Semantic Agent] Canonical schema enrichment completed for connection_id=%d", connection_id)

    return {
        "tables": [
            {"table_name": t.table_name.raw_name, "table_id": table_id_map[t.table_name.raw_name]}
            for t in raw_schema.tables
        ],
        "relationships": relationships,
        "status": "draft",
    }


async def create_metric(
    db: AsyncSession,
    connection_id: int,
    metric_data: dict[str, Any],
    user_id: int,
) -> SemanticMetricModel:
    """Create a new metric with version=1, status='draft', and an initial metric_versions record."""
    definition = MetricDefinition.model_validate(metric_data["definition"])
    definition = with_metric_status(definition, "pending_approval")
    table = await validate_metric_definition(db, connection_id, definition)
    payload = definition.model_dump(mode="json")
    metric = SemanticMetricModel(
        db_id=connection_id,
        created_by=user_id,
        name=definition.metric.name,
        description=definition.metric.excluded_notes,
        sql_template="",
        source=metric_data.get("source", "manual"),
        formula="",
        aggregation_type=definition.metric.formula.function,
        definition=payload,
        base_entity_id=table.id,
        version=1,
        status="pending_approval",
    )
    db.add(metric)
    await db.flush()

    version_record = MetricVersionModel(
        metric_id=metric.id,
        version=1,
        formula="",
        definition=payload,
        changed_by=user_id,
    )
    db.add(version_record)
    await db.flush()

    return metric


async def update_metric(
    db: AsyncSession,
    metric_id: int,
    metric_data: dict[str, Any],
    user_id: int,
) -> SemanticMetricModel:
    """Update an existing metric, increment version, and create a new metric_versions record.

    Raises ValueError if the metric is not found or user is not the owner.
    """
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)
    metric = (await db.execute(stmt)).scalar_one_or_none()
    if metric is None:
        raise ValueError(f"Metric {metric_id} not found")
    if metric.created_by != user_id:
        raise ValueError(f"User {user_id} does not have ownership of metric {metric_id}")

    definition = MetricDefinition.model_validate(metric_data["definition"])
    definition = with_metric_status(definition, "pending_approval")
    table = await validate_metric_definition(db, metric.db_id, definition)
    payload = definition.model_dump(mode="json")
    metric.name = definition.metric.name
    metric.description = definition.metric.excluded_notes
    metric.definition = payload
    metric.base_entity_id = table.id
    metric.aggregation_type = definition.metric.formula.function
    metric.status = "pending_approval"
    metric.approved_by = None
    metric.version += 1

    version_record = MetricVersionModel(
        metric_id=metric.id,
        version=metric.version,
        formula="",
        definition=payload,
        changed_by=user_id,
    )
    db.add(version_record)
    await db.flush()

    return metric


async def approve_metric(
    db: AsyncSession,
    metric_id: int,
    user_id: int,
) -> SemanticMetricModel:
    """Approve a metric: set status='approved' and record approved_by.

    Raises ValueError if the metric is not found.
    """
    stmt = select(SemanticMetricModel).where(SemanticMetricModel.id == metric_id)
    metric = (await db.execute(stmt)).scalar_one_or_none()
    if metric is None:
        raise ValueError(f"Metric {metric_id} not found")

    if metric.definition is None:
        raise ValueError("Legacy metric definition requires review before approval")
    definition = with_metric_status(MetricDefinition.model_validate(metric.definition), "approved")
    metric.definition = definition.model_dump(mode="json")
    metric.status = "approved"
    metric.approved_by = user_id
    await db.flush()

    return metric


async def get_metric_with_history(
    db: AsyncSession,
    metric_id: int,
) -> SemanticMetricModel | None:
    """Retrieve a metric with its version history eagerly loaded.

    Returns None if the metric does not exist.
    """
    stmt = (
        select(SemanticMetricModel)
        .where(SemanticMetricModel.id == metric_id)
        .options(selectinload(SemanticMetricModel.versions))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _call_llm_enrichment(raw_schema: RawSchemaMetadata, dialect: str) -> dict[str, Any]:
    """Call LLM to generate Vietnamese business names for tables and columns."""
    tables_info = []
    for table in raw_schema.tables:
        cols = [{"column_name": c.column_name.raw_name, "data_type": c.data_type} for c in table.columns]
        tables_info.append({"table_name": table.table_name.raw_name, "columns": cols})

    prompt = (
        "Given the following database schema, provide Vietnamese business names and descriptions "
        "for each table and column. Return a JSON object where keys are table names, and values are "
        'objects with "business_name" (Vietnamese), "description" (Vietnamese), and "columns" (array of '
        '{"column_name", "business_name", "description"}).\n\n'
        f"Schema ({dialect}):\n{json.dumps(tables_info, indent=2)}"
    )

    logger.info(
        "[AI Semantic Agent] Sending schema prompt (%d tables, dialect=%s) to LLM...", len(raw_schema.tables), dialect
    )
    llm = get_llm()
    response = await llm.ainvoke(prompt)
    content = str(response.content).strip()
    logger.info("[AI Semantic Agent] Received LLM response (%d chars)", len(content))

    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])

    try:
        res_json = json.loads(content)
        logger.info(
            "[AI Semantic Agent] Successfully parsed LLM response JSON containing %d enriched table definitions",
            len(res_json),
        )
        return res_json
    except json.JSONDecodeError:
        logger.warning("[AI Semantic Agent] LLM enrichment response was not valid JSON, returning empty enrichment")
        return {}


async def _upsert_semantic_table(
    db: AsyncSession,
    connection_id: int,
    table_name: str,
    enrichment: dict[str, Any],
    schema_name: str,
    pk_col: str | None,
    user_id: int,
) -> int:
    """Upsert a semantic table: update if exists (by db_id + table_name), insert otherwise."""
    stmt = select(SemanticTableModel).where(
        SemanticTableModel.db_id == connection_id,
        SemanticTableModel.table_name == table_name,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.business_name = enrichment.get("business_name", table_name)
        existing.description = enrichment.get("description", "")
        existing.physical_schema = schema_name
        existing.primary_key_column = pk_col
        return existing.id

    record = SemanticTableModel(
        db_id=connection_id,
        table_name=table_name,
        business_name=enrichment.get("business_name", table_name),
        description=enrichment.get("description", ""),
        physical_schema=schema_name,
        primary_key_column=pk_col,
        created_by=user_id,
    )
    db.add(record)
    await db.flush()
    return record.id


async def _upsert_semantic_column(
    db: AsyncSession,
    table_id: int,
    col_meta: Any,
    enrichment: dict[str, Any],
) -> int:
    """Upsert a semantic column: update if exists (by table_id + column_name), insert otherwise."""
    col_name = col_meta.column_name.raw_name
    data_type = col_meta.data_type
    is_time = data_type.upper().strip() in _TIME_DIMENSION_TYPES

    stmt = select(SemanticColumnModel).where(
        SemanticColumnModel.table_id == table_id,
        SemanticColumnModel.column_name == col_name,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.business_name = enrichment.get("business_name", col_name)
        existing.description = enrichment.get("description", "")
        existing.is_time_dimension = is_time
        existing.data_type = data_type
        existing.is_primary_key = col_meta.primary_key
        existing.is_nullable = col_meta.nullable
        return existing.id

    record = SemanticColumnModel(
        table_id=table_id,
        column_name=col_name,
        data_type=data_type,
        business_name=enrichment.get("business_name", col_name),
        description=enrichment.get("description", ""),
        is_primary_key=col_meta.primary_key,
        is_nullable=col_meta.nullable,
        is_time_dimension=is_time,
    )
    db.add(record)
    await db.flush()
    return record.id


async def _extract_and_save_relationships(
    db: AsyncSession,
    connection_id: int,
    raw_schema: RawSchemaMetadata,
    table_id_map: dict[str, int],
) -> list[dict[str, str]]:
    """Extract FK relationships from raw_schema and upsert into canonical_relationships."""
    relationships: list[dict[str, str]] = []

    for table_meta in raw_schema.tables:
        from_table_name = table_meta.table_name.raw_name
        from_entity_id = table_id_map.get(from_table_name)
        if from_entity_id is None:
            continue

        for fk in table_meta.foreign_keys:
            to_table_name = fk.referred_table.raw_name
            to_entity_id = table_id_map.get(to_table_name)
            if to_entity_id is None:
                continue

            fk_col = fk.constrained_columns[0].raw_name
            ref_col = fk.referred_columns[0].raw_name
            join_cond = f"{from_table_name}.{fk_col} = {to_table_name}.{ref_col}"

            await _upsert_relationship(db, connection_id, from_entity_id, to_entity_id, join_cond)

            relationships.append(
                {
                    "from_table": from_table_name,
                    "to_table": to_table_name,
                    "join_condition": join_cond,
                    "relationship_type": "many_to_one",
                }
            )

    return relationships


async def _upsert_relationship(
    db: AsyncSession,
    connection_id: int,
    from_entity_id: int,
    to_entity_id: int,
    join_condition: str,
) -> None:
    """Upsert a canonical relationship record."""
    stmt = select(CanonicalRelationshipModel).where(
        CanonicalRelationshipModel.connection_id == connection_id,
        CanonicalRelationshipModel.from_entity_id == from_entity_id,
        CanonicalRelationshipModel.to_entity_id == to_entity_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.join_condition = join_condition
        return

    record = CanonicalRelationshipModel(
        connection_id=connection_id,
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relationship_type="many_to_one",
        join_condition=join_condition,
    )
    db.add(record)


async def delete_semantic_database(
    db: AsyncSession,
    db_id: int,
    user_id: int | None = None,
) -> bool:
    """Delete SemanticDatabaseModel and all linked technical DBs/schemas, tables, metrics, and relationships."""
    stmt = select(SemanticDatabaseModel).where(SemanticDatabaseModel.id == db_id)
    if user_id is not None:
        stmt = stmt.where(SemanticDatabaseModel.created_by == user_id)
    sem_db = (await db.execute(stmt)).scalar_one_or_none()
    if sem_db is None:
        return False

    live_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == db_id)
    for ldb in (await db.execute(live_stmt)).scalars().all():
        await db.delete(ldb)

    imp_stmt = select(ImportedSchemaModel).where(ImportedSchemaModel.semantic_db_id == db_id)
    for imp in (await db.execute(imp_stmt)).scalars().all():
        await db.delete(imp)

    await db.delete(sem_db)
    await db.commit()
    return True
