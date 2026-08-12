"""canonical relationship metadata v2

Revision ID: ce2735d8b117
Revises: a8c9d0e1f234
Create Date: 2026-08-12 21:25:18.559938

"""

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
import sqlglot
from sqlglot import exp

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ce2735d8b117"
down_revision: str | Sequence[str] | None = "a8c9d0e1f234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("canonical_relationships", sa.Column("relationship_key", sa.String(length=500), nullable=True))
    op.add_column("canonical_relationships", sa.Column("constraint_name", sa.String(length=200), nullable=True))
    op.add_column("canonical_relationships", sa.Column("column_pairs", sa.JSON(), nullable=True))
    op.add_column(
        "canonical_relationships",
        sa.Column("validation_status", sa.String(length=20), nullable=False, server_default="needs_review"),
    )
    _backfill_relationships()
    _revalidate_metrics()
    op.alter_column("canonical_relationships", "relationship_key", nullable=False)
    op.alter_column("canonical_relationships", "column_pairs", nullable=False)
    op.drop_constraint(op.f("uq_canonical_rel"), "canonical_relationships", type_="unique")
    op.create_unique_constraint(
        "uq_canonical_rel_key", "canonical_relationships", ["connection_id", "relationship_key"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_canonical_rel_key", "canonical_relationships", type_="unique")
    op.create_unique_constraint(
        op.f("uq_canonical_rel"),
        "canonical_relationships",
        ["connection_id", "from_entity_id", "to_entity_id"],
    )
    op.drop_column("canonical_relationships", "validation_status")
    op.drop_column("canonical_relationships", "column_pairs")
    op.drop_column("canonical_relationships", "constraint_name")
    op.drop_column("canonical_relationships", "relationship_key")


def _backfill_relationships() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    relationships = sa.Table("canonical_relationships", metadata, autoload_with=bind)
    tables = sa.Table("semantic_tables", metadata, autoload_with=bind)
    columns = sa.Table("semantic_columns", metadata, autoload_with=bind)
    table_names = dict(bind.execute(sa.select(tables.c.id, tables.c.table_name)).all())
    column_ids = {
        (row.table_id, row.column_name): row.id
        for row in bind.execute(sa.select(columns.c.id, columns.c.table_id, columns.c.column_name))
    }
    for row in bind.execute(sa.select(relationships)).mappings():
        values = _relationship_values(row, table_names, column_ids)
        bind.execute(relationships.update().where(relationships.c.id == row["id"]).values(**values))


def _relationship_values(
    row: sa.RowMapping,
    table_names: dict[int, str],
    column_ids: dict[tuple[int, str], int],
) -> dict[str, Any]:
    key = f"legacy:{row['id']}:{row['from_entity_id']}:{row['to_entity_id']}"
    match = re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_$]*\\.([A-Za-z_][A-Za-z0-9_$]*)\\s*=\\s*"
        r"[A-Za-z_][A-Za-z0-9_$]*\\.([A-Za-z_][A-Za-z0-9_$]*)",
        row["join_condition"].strip(),
    )
    if not match:
        return {"relationship_key": key, "column_pairs": [], "validation_status": "needs_review"}
    source_id = column_ids.get((row["from_entity_id"], match.group(1)))
    target_id = column_ids.get((row["to_entity_id"], match.group(2)))
    if not source_id or not target_id:
        return {"relationship_key": key, "column_pairs": [], "validation_status": "needs_review"}
    source = table_names.get(row["from_entity_id"], "source")
    target = table_names.get(row["to_entity_id"], "target")
    return {
        "relationship_key": f"legacy:{source}:{match.group(1)}:{target}:{match.group(2)}",
        "column_pairs": [{"from_column_id": source_id, "to_column_id": target_id}],
        "validation_status": "valid",
    }


def _revalidate_metrics() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    metrics = sa.Table("semantic_metrics", metadata, autoload_with=bind)
    versions = sa.Table("metric_versions", metadata, autoload_with=bind)
    tables = sa.Table("semantic_tables", metadata, autoload_with=bind)
    columns = sa.Table("semantic_columns", metadata, autoload_with=bind)
    table_rows = {row.id: row for row in bind.execute(sa.select(tables))}
    column_rows = list(bind.execute(sa.select(columns)))
    for row in bind.execute(sa.select(metrics)).mappings():
        payload, valid = _resolved_metric(row, table_rows, column_rows)
        version = int(row.get("version") or 1) + 1
        status = row["status"] if valid else "needs_review"
        approved_by = row.get("approved_by") if valid else None
        bind.execute(
            metrics.update()
            .where(metrics.c.id == row["id"])
            .values(
                definition=payload,
                status=status,
                approved_by=approved_by,
                version=version,
            )
        )
        bind.execute(
            versions.insert().values(
                metric_id=row["id"],
                version=version,
                formula="",
                definition=payload,
                changed_by=None,
                change_reason="automatic canonicalization",
                created_at=datetime.now(UTC),
            )
        )


def _resolved_metric(
    row: sa.RowMapping,
    tables: dict[int, Any],
    columns: list[Any],
) -> tuple[dict[str, Any] | None, bool]:
    definition = row.get("definition")
    table = tables.get(row.get("base_entity_id"))
    if not isinstance(definition, dict) or table is None:
        return definition, False
    metric = definition.get("metric")
    if not isinstance(metric, dict):
        return definition, False
    table_columns = [item for item in columns if item.table_id == table.id]
    by_name = {item.column_name.lower(): item for item in table_columns}
    try:
        expression = metric["formula"]["expression"]
        expression_ast = _migration_expression(expression, by_name)
        filters = [_resolved_filter(item, by_name) for item in metric.get("filters", [])]
    except (KeyError, TypeError, ValueError, sqlglot.errors.ParseError):
        return definition, False
    grain = [item.id for item in table_columns if item.is_primary_key]
    if not grain and table.primary_key_column:
        primary = by_name.get(table.primary_key_column.lower())
        grain = [primary.id] if primary else []
    metric["formula"]["expression_ast"] = expression_ast
    metric["base_entity"] = table.table_name
    metric["base_entity_id"] = table.id
    metric["grain"] = {"column_ids": grain}
    metric["filters"] = filters
    diagnostics = [] if grain else [{"code": "MISSING_GRAIN", "message": "Base entity has no grain"}]
    metric["status"] = metric.get("status") if grain else "needs_review"
    return {"schema_version": 2, "metric": metric, "diagnostics": diagnostics}, bool(grain)


def _resolved_filter(item: dict[str, Any], columns: dict[str, Any]) -> dict[str, Any]:
    column = columns[item["field"].lower()]
    return {**item, "field": column.column_name, "column_id": column.id}


def _migration_expression(expression: str, columns: dict[str, Any]) -> dict[str, Any]:
    if expression == "*":
        return {"kind": "literal", "value": 1}
    return _migration_node(sqlglot.parse_one(expression), columns)


def _migration_node(node: exp.Expression, columns: dict[str, Any]) -> dict[str, Any]:
    if isinstance(node, exp.Column):
        return {"kind": "column", "column_id": columns[node.name.lower()].id}
    if isinstance(node, exp.Literal) and node.is_number:
        return {"kind": "literal", "value": float(node.this)}
    if isinstance(node, exp.Paren):
        return _migration_node(node.this, columns)
    if isinstance(node, exp.Neg):
        return {"kind": "neg", "children": [_migration_node(node.this, columns)]}
    kinds = {exp.Add: "add", exp.Sub: "sub", exp.Mul: "mul", exp.Div: "div"}
    for node_type, kind in kinds.items():
        if isinstance(node, node_type):
            return {
                "kind": kind,
                "children": [
                    _migration_node(node.this, columns),
                    _migration_node(node.expression, columns),
                ],
            }
    raise ValueError("Unsupported legacy metric expression")
