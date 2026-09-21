"""Schema Self-Healing Service.

Automatically detects schema drift, rewrites metric formulas using sqlglot AST,
preserves Vietnamese business names and descriptions, marks deprecated items,
and writes audit records.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlglot import exp, parse_one

from src.models.db import (
    CanonicalRelationshipModel,
    LiveTargetDbModel,
    MetricVersionModel,
    SchemaSyncLogModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    utc_now,
)
from src.models.review_mixin import REVIEW_STATUS_PENDING
from src.models.schema_metadata import RawSchemaMetadata, SchemaDialect
from src.services.database import decrypt_conn_url
from src.services.live_db_service import introspect_live_database, resolve_and_validate_dialect
from src.services.schema_fingerprint import compute_schema_fingerprint

logger = logging.getLogger(__name__)


def heal_sql_formula_ast(formula: str, old_col: str, new_col: str, dialect: str = "postgres") -> str:
    """Rewrite column references in a SQL formula using sqlglot AST."""
    if not formula:
        return formula
    try:
        parsed = parse_one(formula, read=dialect)
        for node in parsed.walk():
            if isinstance(node, exp.Column) and node.name.lower() == old_col.lower():
                node.set("this", exp.to_identifier(new_col))
            elif isinstance(node, exp.Identifier) and node.name.lower() == old_col.lower():
                node.set("this", new_col)
        return parsed.sql(dialect=dialect)
    except Exception as exc:
        logger.debug("AST rewrite fallback for formula '%s': %s", formula, exc)
        return formula.replace(old_col, new_col)


def _heal_metric_definition_dict(
    definition: dict[str, Any] | None, old_col: str, new_col: str, dialect: str
) -> dict[str, Any] | None:
    """Update column references inside metric definition JSON recursively."""
    if not definition:
        return definition

    def _heal_node(node: Any) -> Any:
        if isinstance(node, dict):
            new_dict = {}
            for k, v in node.items():
                if k == "expression" and isinstance(v, str):
                    new_dict[k] = heal_sql_formula_ast(v, old_col, new_col, dialect)
                elif k in ("base_column", "field") and isinstance(v, str) and v.lower() == old_col.lower():
                    new_dict[k] = new_col
                else:
                    new_dict[k] = _heal_node(v)
            return new_dict
        if isinstance(node, list):
            return [_heal_node(item) for item in node]
        return node

    return _heal_node(definition)


def _match_renamed_columns(
    dropped_cols: list[SemanticColumnModel], new_cols: list[Any]
) -> list[tuple[SemanticColumnModel, Any]]:
    """Match renamed columns by count, type, or position heuristic."""
    pairs: list[tuple[SemanticColumnModel, Any]] = []
    if len(dropped_cols) == 1 and len(new_cols) == 1:
        pairs.append((dropped_cols[0], new_cols[0]))
        return pairs

    matched_new = set()
    for d_col in dropped_cols:
        d_type = str(d_col.data_type).lower().split("(")[0]
        for n_col in new_cols:
            if n_col.column_name.raw_name in matched_new:
                continue
            n_type = str(n_col.data_type).lower().split("(")[0]
            if d_type == n_type:
                pairs.append((d_col, n_col))
                matched_new.add(n_col.column_name.raw_name)
                break
    return pairs


def _match_renamed_tables(
    dropped_tables: list[SemanticTableModel],
    raw_tables: list[Any],
) -> list[tuple[SemanticTableModel, Any]]:
    """Match renamed tables based on matching column sets with sufficient overlap."""
    pairs: list[tuple[SemanticTableModel, Any]] = []
    matched_raw = set()
    for d_tbl in dropped_tables:
        d_cols = {c.column_name.lower() for c in d_tbl.columns}
        best_match = None
        best_score = 0.0
        for r_tbl in raw_tables:
            r_name = r_tbl.table_name.raw_name
            if r_name in matched_raw:
                continue
            r_cols = {c.column_name.raw_name.lower() for c in r_tbl.columns}
            if not d_cols or not r_cols:
                continue
            overlap = len(d_cols.intersection(r_cols)) / max(len(d_cols), len(r_cols))
            if overlap >= 0.5 and overlap > best_score:
                best_score = overlap
                best_match = r_tbl
        if best_match is not None:
            pairs.append((d_tbl, best_match))
            matched_raw.add(best_match.table_name.raw_name)
    return pairs


def detect_drift_details(existing_tables: list[SemanticTableModel], raw_schema: RawSchemaMetadata) -> dict[str, Any]:
    """Compare database tables/columns against raw schema metadata to classify changes."""
    raw_tbl_map = {t.table_name.raw_name.lower(): t for t in raw_schema.tables}
    exist_tbl_map = {t.table_name.lower(): t for t in existing_tables}

    unmatched_added_tbls = [t for t in raw_schema.tables if t.table_name.raw_name.lower() not in exist_tbl_map]
    unmatched_dropped_tbls = [t for t in existing_tables if t.table_name.lower() not in raw_tbl_map]

    # Detect renamed tables
    renamed_tbl_pairs = _match_renamed_tables(unmatched_dropped_tbls, unmatched_added_tbls)
    matched_dropped_tbl_ids = {p[0].id for p in renamed_tbl_pairs}
    matched_added_tbl_names = {p[1].table_name.raw_name for p in renamed_tbl_pairs}

    renamed_tables = [
        {
            "table_id": old_t.id,
            "old_name": old_t.table_name,
            "new_name": new_t.table_name.raw_name,
        }
        for old_t, new_t in renamed_tbl_pairs
    ]

    added_tables = [
        t.table_name.raw_name for t in unmatched_added_tbls if t.table_name.raw_name not in matched_added_tbl_names
    ]
    dropped_tables = [t.table_name for t in unmatched_dropped_tbls if t.id not in matched_dropped_tbl_ids]

    renamed_cols = []
    added_cols = []
    dropped_cols = []
    type_changes = []

    for t_name_lower, exist_tbl in exist_tbl_map.items():
        if t_name_lower not in raw_tbl_map:
            continue
        raw_tbl = raw_tbl_map[t_name_lower]
        raw_col_map = {c.column_name.raw_name.lower(): c for c in raw_tbl.columns}
        exist_col_map = {c.column_name.lower(): c for c in exist_tbl.columns}

        unmatched_exist = [c for name, c in exist_col_map.items() if name not in raw_col_map]
        unmatched_raw = [c for name, c in raw_col_map.items() if name not in exist_col_map]

        # Check type changes for existing matched columns
        for name_lower, exist_c in exist_col_map.items():
            if name_lower in raw_col_map:
                raw_c = raw_col_map[name_lower]
                if str(exist_c.data_type).lower() != str(raw_c.data_type).lower():
                    type_changes.append(
                        {
                            "table_name": exist_tbl.table_name,
                            "col_id": exist_c.id,
                            "column_name": exist_c.column_name,
                            "old_type": exist_c.data_type,
                            "new_type": raw_c.data_type,
                        }
                    )

        pairs = _match_renamed_columns(unmatched_exist, unmatched_raw)
        matched_exist_ids = {p[0].id for p in pairs}
        matched_raw_names = {p[1].column_name.raw_name for p in pairs}

        for old_c, new_c in pairs:
            renamed_cols.append(
                {
                    "table_name": exist_tbl.table_name,
                    "table_id": exist_tbl.id,
                    "col_id": old_c.id,
                    "old_name": old_c.column_name,
                    "new_name": new_c.column_name.raw_name,
                    "new_type": new_c.data_type,
                }
            )
        for c in unmatched_exist:
            if c.id not in matched_exist_ids:
                dropped_cols.append({"table_name": exist_tbl.table_name, "col_id": c.id, "name": c.column_name})
        for c in unmatched_raw:
            if c.column_name.raw_name not in matched_raw_names:
                added_cols.append(
                    {"table_name": exist_tbl.table_name, "name": c.column_name.raw_name, "type": c.data_type}
                )

    return {
        "renamed_tables": renamed_tables,
        "added_tables": added_tables,
        "dropped_tables": dropped_tables,
        "renamed_columns": renamed_cols,
        "added_columns": added_cols,
        "dropped_columns": dropped_cols,
        "type_changes": type_changes,
    }


def _extract_formula_str(metric: SemanticMetricModel) -> str:
    """Extract a human-readable formula from metric.formula or definition JSON."""
    if metric.formula and metric.formula.strip():
        return metric.formula.strip()
    if metric.definition and isinstance(metric.definition, dict):
        m = metric.definition.get("metric", metric.definition)
        if isinstance(m, dict) and "formula" in m and isinstance(m["formula"], dict):
            fn = m["formula"].get("function", "")
            expr = m["formula"].get("expression", "")
            if fn and expr:
                return f"{fn}({expr})"
            return expr or fn
    return "COUNT(*)"


async def _heal_metric_for_rename(
    db: AsyncSession,
    metric: SemanticMetricModel,
    old_col: str,
    new_col: str,
    dialect: str,
) -> dict[str, Any] | None:
    """Heal a single metric for a renamed column."""
    def_str = str(metric.definition or "").lower()
    needs_heal = (
        old_col.lower() in metric.formula.lower()
        or old_col.lower() in metric.sql_template.lower()
        or old_col.lower() in def_str
    )
    if not needs_heal:
        return None

    old_formula = _extract_formula_str(metric)
    new_formula = heal_sql_formula_ast(old_formula, old_col, new_col, dialect)
    metric.formula = new_formula
    metric.sql_template = new_formula
    metric.definition = _heal_metric_definition_dict(metric.definition, old_col, new_col, dialect)
    metric.version += 1

    tbl_name = metric.base_entity.table_name if metric.base_entity else "order_header"
    old_sql = f'SELECT {old_formula} AS "{metric.name}" FROM {tbl_name} LIMIT 100;'  # noqa: S608
    new_sql = f'SELECT {new_formula} AS "{metric.name}" FROM {tbl_name} LIMIT 100;'  # noqa: S608

    version_entry = MetricVersionModel(
        metric_id=metric.id,
        version=metric.version,
        name=metric.name,
        formula=metric.formula,
        definition=metric.definition,
        status="approved",
        change_reason=f"Auto-healed: renamed column '{old_col}' -> '{new_col}'",
    )
    db.add(version_entry)
    return {
        "metric_id": metric.id,
        "name": metric.name,
        "table_name": tbl_name,
        "old_formula": old_formula,
        "new_formula": new_formula,
        "old_sql": old_sql,
        "new_sql": new_sql,
    }


async def _heal_relationships_for_rename(
    db: AsyncSession, semantic_db_id: int, old_col: str, new_col: str, dialect: str
) -> None:
    """Rewrite join conditions in canonical relationships for renamed columns."""
    stmt = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == semantic_db_id)
    rels = (await db.execute(stmt)).scalars().all()
    for rel in rels:
        if old_col.lower() in rel.join_condition.lower():
            rel.join_condition = heal_sql_formula_ast(rel.join_condition, old_col, new_col, dialect)


async def _apply_renamed_columns(
    db: AsyncSession,
    semantic_db_id: int,
    renamed_cols: list[dict[str, Any]],
    dialect: str,
) -> list[dict[str, Any]]:
    """Apply column renaming in metadata and heal dependent metrics."""
    healed_metrics = []
    metric_stmt = (
        select(SemanticMetricModel)
        .where(
            SemanticMetricModel.db_id == semantic_db_id,
            SemanticMetricModel.is_deleted.is_(False),
            SemanticMetricModel.status == "approved",
        )
        .options(selectinload(SemanticMetricModel.base_entity))
    )
    metrics = (await db.execute(metric_stmt)).scalars().all()

    for item in renamed_cols:
        col = await db.get(SemanticColumnModel, item["col_id"])
        if col:
            col.column_name = item["new_name"]
            col.data_type = item.get("new_type", col.data_type)

        for m in metrics:
            healed = await _heal_metric_for_rename(db, m, item["old_name"], item["new_name"], dialect)
            if healed:
                healed_metrics.append(healed)

        await _heal_relationships_for_rename(db, semantic_db_id, item["old_name"], item["new_name"], dialect)
    return healed_metrics


async def _handle_dropped_items(
    db: AsyncSession,
    semantic_db_id: int,
    dropped_cols: list[dict[str, Any]],
    dropped_tbls: list[str],
) -> None:
    """Mark dropped tables and columns as [Deprecated] and flag dependent metrics."""
    for item in dropped_cols:
        col = await db.get(SemanticColumnModel, item["col_id"])
        if col and not col.business_name.startswith("[Deprecated]"):
            col.business_name = f"[Deprecated] {col.business_name}"
            col.review_status = REVIEW_STATUS_PENDING

    for tbl_name in dropped_tbls:
        stmt = select(SemanticTableModel).where(
            SemanticTableModel.db_id == semantic_db_id,
            SemanticTableModel.table_name == tbl_name,
        )
        tbl = (await db.execute(stmt)).scalar_one_or_none()
        if tbl:
            m_stmt = select(SemanticMetricModel).where(
                SemanticMetricModel.db_id == semantic_db_id,
                SemanticMetricModel.base_entity_id == tbl.id,
                SemanticMetricModel.is_deleted.is_(False),
            )
            tbl_metrics = (await db.execute(m_stmt)).scalars().all()
            for m in tbl_metrics:
                if m.source == "auto_sync" and m.status != "approved":
                    m.is_deleted = True
                elif m.status == "approved":
                    m.status = "needs_review"
                    m.version += 1
                    reason = f"Cảnh báo: Bảng nguồn '{tbl_name}' đã bị xóa khỏi Database."
                    db.add(
                        MetricVersionModel(
                            metric_id=m.id,
                            version=m.version,
                            name=m.name,
                            formula=m.formula,
                            definition=m.definition,
                            status="needs_review",
                            change_reason=reason,
                        )
                    )

            col_stmt = select(SemanticColumnModel).where(SemanticColumnModel.table_id == tbl.id)
            for col in (await db.execute(col_stmt)).scalars().all():
                await db.delete(col)
            await db.delete(tbl)


async def _handle_added_items(
    db: AsyncSession,
    semantic_db_id: int,
    raw_schema: RawSchemaMetadata,
    added_tbls: list[str],
    added_cols: list[dict[str, Any]],
) -> None:
    """Ingest newly added tables and columns with pending review status."""
    tbl_by_name = {t.table_name.raw_name: t for t in raw_schema.tables}
    for t_name in added_tbls:
        t_meta = tbl_by_name.get(t_name)
        if not t_meta:
            continue
        new_tbl = SemanticTableModel(
            db_id=semantic_db_id,
            table_name=t_name,
            business_name=f"Bảng {t_name}",
            description=f"Bảng dữ liệu mới phát hiện: {t_name}",
            review_status=REVIEW_STATUS_PENDING,
        )
        db.add(new_tbl)
        await db.flush()

        pk_cols = set()
        if t_meta.primary_key:
            pk_cols = {col.raw_name for col in t_meta.primary_key.constrained_columns}

        fk_map: dict[str, tuple[str, str]] = {}
        if t_meta.foreign_keys:
            for fk in t_meta.foreign_keys:
                target_table = fk.referred_table.raw_name
                target_tbl = (
                    await db.execute(
                        select(SemanticTableModel).where(
                            SemanticTableModel.db_id == semantic_db_id,
                            SemanticTableModel.table_name == target_table,
                        )
                    )
                ).scalar_one_or_none()
                target_id = target_tbl.id if target_tbl else None
                for l_col, r_col in zip(fk.constrained_columns, fk.referred_columns, strict=False):
                    fk_map[l_col.raw_name] = (target_table, r_col.raw_name)
                    if target_id is None:
                        continue
                    db.add(
                        CanonicalRelationshipModel(
                            connection_id=semantic_db_id,
                            from_entity_id=new_tbl.id,
                            to_entity_id=target_id,
                            relationship_type="many_to_one",
                            join_condition=f"{t_name}.{l_col.raw_name} = {target_table}.{r_col.raw_name}",
                            business_name=f"{t_name} → {target_table}",
                            description=f"Mỗi {t_name} liên kết với {target_table}",
                            review_status=REVIEW_STATUS_PENDING,
                            validation_status="valid",
                        )
                    )

        for c in t_meta.columns:
            c_name = c.column_name.raw_name
            is_pk = c_name in pk_cols
            is_fk = c_name in fk_map
            fk_target_t, fk_target_c = fk_map.get(c_name, (None, None))
            db.add(
                SemanticColumnModel(
                    table_id=new_tbl.id,
                    column_name=c_name,
                    data_type=c.data_type,
                    business_name=c_name,
                    description=f"Cột {c_name}",
                    is_primary_key=is_pk,
                    is_foreign_key=is_fk,
                    fk_target_table=fk_target_t,
                    fk_target_column=fk_target_c,
                    review_status=REVIEW_STATUS_PENDING,
                )
            )

        # Auto-enrich: suggest a starter metric for the new table
        m_def = {
            "schema_version": 2,
            "metric": {
                "name": f"Tổng số {t_name}",
                "base_entity": t_name,
                "base_entity_id": new_tbl.id,
                "formula": {"function": "COUNT", "expression": "*"},
            },
        }
        new_metric = SemanticMetricModel(
            db_id=semantic_db_id,
            base_entity_id=new_tbl.id,
            name=f"Tổng số {t_name}",
            description=f"Tổng số bản ghi trong bảng {t_name} (tự động gợi ý từ schema sync)",
            formula="COUNT(*)",
            sql_template="COUNT(*)",
            aggregation_type="count",
            source="auto_sync",
            status="pending_approval",
            definition=m_def,
            version=1,
        )
        db.add(new_metric)
        await db.flush()

        db.add(
            MetricVersionModel(
                metric_id=new_metric.id,
                version=1,
                name=f"Tổng số {t_name}",
                formula="COUNT(*)",
                definition=m_def,
                status="pending_approval",
                change_reason="Tự động gợi ý từ schema auto-sync",
            )
        )

    exist_tbls_stmt = select(SemanticTableModel).where(SemanticTableModel.db_id == semantic_db_id)
    existing_tbls = {t.table_name: t for t in (await db.execute(exist_tbls_stmt)).scalars().all()}
    for item in added_cols:
        tbl = existing_tbls.get(item["table_name"])
        if tbl:
            db.add(
                SemanticColumnModel(
                    table_id=tbl.id,
                    column_name=item["name"],
                    data_type=item["type"],
                    business_name=item["name"],
                    description=f"Cột mới phát hiện {item['name']}",
                    review_status=REVIEW_STATUS_PENDING,
                )
            )


async def _apply_renamed_tables(
    db: AsyncSession,
    semantic_db_id: int,
    renamed_tables: list[dict[str, Any]],
    dialect: str,
) -> list[dict[str, Any]]:
    """Update renamed table names, relationships, and linked metric definitions."""
    results = []
    for item in renamed_tables:
        tbl = await db.get(SemanticTableModel, item["table_id"])
        if tbl:
            tbl.table_name = item["new_name"]
            tbl.business_name = f"Bảng {item['new_name']}"

        old_t = item["old_name"]
        new_t = item["new_name"]
        rel_stmt = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == semantic_db_id)
        rels = (await db.execute(rel_stmt)).scalars().all()
        for rel in rels:
            if rel.from_entity.lower() == old_t.lower():
                rel.from_entity = new_t
            if rel.to_entity.lower() == old_t.lower():
                rel.to_entity = new_t
            if old_t.lower() in rel.join_condition.lower():
                rel.join_condition = rel.join_condition.replace(old_t, new_t)

        results.append(item)
    return results


async def _handle_dropped_columns_for_metrics(
    db: AsyncSession,
    semantic_db_id: int,
    dropped_cols: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flag metrics whose source columns were dropped from the database."""
    broken_metrics = []
    if not dropped_cols:
        return broken_metrics

    metric_stmt = (
        select(SemanticMetricModel)
        .where(
            SemanticMetricModel.db_id == semantic_db_id,
            SemanticMetricModel.is_deleted.is_(False),
        )
        .options(selectinload(SemanticMetricModel.base_entity))
    )
    metrics = (await db.execute(metric_stmt)).scalars().all()

    for item in dropped_cols:
        col_name = item["name"]
        tbl_name = item["table_name"]
        for m in metrics:
            def_str = str(m.definition or "").lower()
            if col_name.lower() in m.formula.lower() or col_name.lower() in def_str:
                if m.status != "needs_review":
                    m.status = "needs_review"
                    m.version += 1
                    reason = f"Cảnh báo: Cột nguồn '{col_name}' trong bảng '{tbl_name}' đã bị xóa khỏi Database."
                    version_entry = MetricVersionModel(
                        metric_id=m.id,
                        version=m.version,
                        name=m.name,
                        formula=m.formula,
                        definition=m.definition,
                        status="needs_review",
                        change_reason=reason,
                    )
                    db.add(version_entry)
                    broken_metrics.append(
                        {
                            "metric_id": m.id,
                            "name": m.name,
                            "table_name": tbl_name,
                            "column_name": col_name,
                            "reason": reason,
                        }
                    )
    return broken_metrics


async def _apply_type_changes(
    db: AsyncSession,
    type_changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Update column data types in semantic columns."""
    for item in type_changes:
        col = await db.get(SemanticColumnModel, item["col_id"])
        if col:
            col.data_type = item["new_type"]
    return type_changes


async def execute_self_healing(
    db: AsyncSession,
    semantic_db_id: int,
    trigger_type: str = "instant_check",
) -> SchemaSyncLogModel:
    """Introspect live target database, perform drift analysis, self-heal, and record audit log."""
    sem_db = await db.get(SemanticDatabaseModel, semantic_db_id)
    if not sem_db:
        raise ValueError(f"Semantic database {semantic_db_id} not found")

    live_db_stmt = select(LiveTargetDbModel).where(LiveTargetDbModel.semantic_db_id == semantic_db_id)
    live_db = (await db.execute(live_db_stmt)).scalar_one_or_none()
    if not live_db:
        log = SchemaSyncLogModel(
            semantic_db_id=semantic_db_id,
            trigger_type=trigger_type,
            status="no_change",
            details="No linked live database found for schema sync.",
        )
        db.add(log)
        await db.commit()
        return log

    conn_url = decrypt_conn_url(live_db.conn_url_enc)
    resolved_dialect = resolve_and_validate_dialect(conn_url, live_db.dialect)
    raw_schema = introspect_live_database(conn_url, resolved_dialect)
    new_fp = compute_schema_fingerprint(raw_schema)
    old_fp = sem_db.schema_fingerprint

    if old_fp == new_fp:
        sem_db.last_synced_at = utc_now()
        sem_db.sync_status = "synced"
        log = SchemaSyncLogModel(
            semantic_db_id=semantic_db_id,
            live_db_id=live_db.id,
            trigger_type=trigger_type,
            status="no_change",
            old_fingerprint=old_fp,
            new_fingerprint=new_fp,
            changes_summary={},
            details="Schema is up to date. No changes detected.",
        )
        db.add(log)
        await db.commit()
        return log

    tbls_stmt = select(SemanticTableModel).where(SemanticTableModel.db_id == semantic_db_id)
    existing_tables = (await db.execute(tbls_stmt)).scalars().all()
    for t in existing_tables:
        await db.refresh(t, ["columns"])

    drift = detect_drift_details(existing_tables, raw_schema)
    dialect_str = (
        "postgres"
        if resolved_dialect == SchemaDialect.POSTGRESQL
        else ("mysql" if resolved_dialect == SchemaDialect.MYSQL else "sqlite")
    )

    healed_metrics = await _apply_renamed_columns(db, semantic_db_id, drift["renamed_columns"], dialect_str)
    renamed_tables_applied = await _apply_renamed_tables(
        db, semantic_db_id, drift.get("renamed_tables", []), dialect_str
    )
    broken_metrics = await _handle_dropped_columns_for_metrics(db, semantic_db_id, drift.get("dropped_columns", []))
    type_changes_applied = await _apply_type_changes(db, drift.get("type_changes", []))

    await _handle_dropped_items(db, semantic_db_id, drift["dropped_columns"], drift["dropped_tables"])
    await _handle_added_items(db, semantic_db_id, raw_schema, drift["added_tables"], drift["added_columns"])

    # Clean up any leftover deprecated tables not present in live database
    live_table_names = {t.table_name.raw_name.lower() for t in raw_schema.tables}
    for t in existing_tables:
        if t.table_name.lower() not in live_table_names or t.business_name.startswith("[Deprecated]"):
            col_stmt = select(SemanticColumnModel).where(SemanticColumnModel.table_id == t.id)
            for col in (await db.execute(col_stmt)).scalars().all():
                await db.delete(col)
            await db.delete(t)

    live_db.schema_metadata = raw_schema.model_dump(mode="json")
    sem_db.schema_fingerprint = new_fp
    sem_db.last_synced_at = utc_now()
    sem_db.sync_status = "synced"

    changes_summary = {
        **drift,
        "healed_metrics": healed_metrics,
        "renamed_tables": renamed_tables_applied,
        "broken_metrics": broken_metrics,
        "type_changes": type_changes_applied,
    }
    status = (
        "healed"
        if (healed_metrics or drift["renamed_columns"] or renamed_tables_applied or broken_metrics)
        else "success"
    )

    summary_parts = []
    if drift.get("added_tables"):
        summary_parts.append(f"{len(drift['added_tables'])} bảng mới (+{', '.join(drift['added_tables'])})")
    if drift.get("dropped_tables"):
        summary_parts.append(f"{len(drift['dropped_tables'])} bảng bị xóa (-{', '.join(drift['dropped_tables'])})")
    if drift.get("added_columns"):
        col_names = [
            f"{c.get('table_name', '')}.{c.get('name', '')}" if c.get("table_name") else c.get("name", "")
            for c in drift["added_columns"]
        ]
        summary_parts.append(f"{len(drift['added_columns'])} cột mới (+{', '.join(col_names)})")
    if drift.get("dropped_columns"):
        col_names = [
            f"{c.get('table_name', '')}.{c.get('name', '')}" if c.get("table_name") else c.get("name", "")
            for c in drift["dropped_columns"]
        ]
        summary_parts.append(f"{len(drift['dropped_columns'])} cột bị xóa (-{', '.join(col_names)})")
    if drift.get("renamed_columns"):
        summary_parts.append(f"{len(drift['renamed_columns'])} cột đổi tên")
    if healed_metrics:
        summary_parts.append(f"{len(healed_metrics)} chỉ số tự vá")
    if renamed_tables_applied:
        summary_parts.append(f"{len(renamed_tables_applied)} bảng đổi tên")
    if broken_metrics:
        summary_parts.append(f"{len(broken_metrics)} chỉ số cần rà soát do mất cột")
    if type_changes_applied:
        summary_parts.append(f"{len(type_changes_applied)} cột đổi kiểu dữ liệu")

    desc_text = ", ".join(summary_parts) if summary_parts else "Đồng bộ cấu trúc hoàn tất."

    log = SchemaSyncLogModel(
        semantic_db_id=semantic_db_id,
        live_db_id=live_db.id,
        trigger_type=trigger_type,
        status=status,
        old_fingerprint=old_fp,
        new_fingerprint=new_fp,
        changes_summary=changes_summary,
        details=f"Auto-sync completed ({status}): {desc_text}",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
