"""Compile approved metric definitions into parameterized read-only SQL."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import sqlglot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
)
from src.models.metric_definition import MetricDefinition, MetricExpressionNode, MetricFilter
from src.models.schemas import DimensionSelection, SemanticQueryFilter, SemanticQuerySpec
from src.services.semantic_compile_error import SemanticCompileError


@dataclass
class CompiledQuery:
    """Hold compiled SQL, bound values, and observable metadata."""

    sql: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def _query_spec(
    query: SemanticQuerySpec | list[int] | None,
    metric_ids: list[int] | None,
    dimension_ids: list[int] | None,
    filters: list[SemanticQueryFilter] | None,
    limit: int,
) -> SemanticQuerySpec:
    """Normalize legacy compiler arguments into the canonical input."""
    if isinstance(query, SemanticQuerySpec):
        return query
    selected_metrics = query if isinstance(query, list) else metric_ids
    dimensions = [DimensionSelection(column_id=item) for item in dimension_ids or []]
    return SemanticQuerySpec(
        metric_ids=selected_metrics or [],
        dimensions=dimensions,
        filters=filters or [],
        limit=min(limit, 1000),
    )


def _reject_duplicate_selections(spec: SemanticQuerySpec) -> None:
    metric_ids = spec.metric_ids
    dimension_ids = [item.column_id for item in spec.dimensions]
    if len(metric_ids) != len(set(metric_ids)) or len(dimension_ids) != len(set(dimension_ids)):
        raise SemanticCompileError("DUPLICATE_SELECTION", "Semantic selections must be unique")


def validate_read_only(sql: str) -> bool:
    """Require exactly one SELECT without write-capable AST nodes."""
    try:
        statements = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"Invalid SQL: {exc}") from exc
    if len(statements) != 1:
        raise ValueError("Multi-statement queries are not allowed")
    if not isinstance(statements[0], exp.Select):
        raise ValueError(f"Only SELECT statements are allowed, got {type(statements[0]).__name__}")
    parsed = statements[0]
    if parsed.find(exp.Into):
        raise ValueError("SELECT INTO is not allowed")
    dml = (exp.Insert, exp.Update, exp.Delete)
    if any(isinstance(node, dml) for node in parsed.walk()):
        raise ValueError("CTE containing DML is not allowed")
    ddl = (exp.Drop, exp.Alter, exp.TruncateTable)
    if any(isinstance(node, ddl) for node in parsed.walk()):
        raise ValueError("DDL is not allowed")
    return True


class SemanticQueryCompiler:
    """Compile approved definitions and selected dimensions through one interface."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compile(
        self,
        connection_id: int,
        query: SemanticQuerySpec | list[int] | None = None,
        dimension_ids: list[int] | None = None,
        filters: list[SemanticQueryFilter] | None = None,
        limit: int = 100,
        *,
        metric_ids: list[int] | None = None,
    ) -> CompiledQuery:
        """Compile semantic selections without accepting SQL from the caller."""
        spec = _query_spec(query, metric_ids, dimension_ids, filters, limit)
        _reject_duplicate_selections(spec)
        return await self._compile_spec(connection_id, spec)

    async def _compile_spec(self, connection_id: int, spec: SemanticQuerySpec) -> CompiledQuery:
        dialect = await self._load_dialect(connection_id)
        metrics = await self._load_metrics(connection_id, spec.metric_ids)
        definitions = _canonical_definitions(metrics)
        base_name = self._require_same_base(definitions)
        tables = await self._load_tables(connection_id)
        table_by_id = {table.id: table for table in tables}
        table_by_name = {table.table_name: table for table in tables}
        base = table_by_name.get(base_name)
        if base is None:
            raise ValueError(f"Unknown base entity: {base_name}")
        dimensions = await self._load_dimensions(connection_id, [item.column_id for item in spec.dimensions])
        base_columns = await self._load_base_columns(base.id)
        _apply_time_grains(dimensions, spec.dimensions)
        runtime_filters = await self._load_runtime_filters(connection_id, spec.filters)
        joins = await self._resolve_joins(connection_id, base, dimensions + runtime_filters, table_by_id)
        return self._build_query(
            dialect, metrics, definitions, base, base_columns, dimensions, joins, runtime_filters, spec.limit
        )

    async def _load_dialect(self, connection_id: int) -> str:
        record = await self._db.get(SemanticDatabaseModel, connection_id)
        if record is None:
            raise SemanticCompileError("UNKNOWN_REFERENCE", "Semantic database not found")
        return {"postgresql": "postgres", "mysql": "mysql", "sqlite": "sqlite"}.get(record.db_type, record.db_type)

    async def _load_metrics(self, db_id: int, ids: list[int]) -> list[SemanticMetricModel]:
        result = await self._db.execute(
            select(SemanticMetricModel).where(
                SemanticMetricModel.db_id == db_id,
                SemanticMetricModel.id.in_(ids),
            )
        )
        found = {item.id: item for item in result.scalars().all()}
        if missing := set(ids) - found.keys():
            raise SemanticCompileError("UNKNOWN_REFERENCE", "Metrics not found", {"metric_ids": sorted(missing)})
        metrics = [found[item_id] for item_id in ids]
        for metric in metrics:
            if metric.status != "approved" or metric.definition is None:
                code = "METRIC_NEEDS_REVIEW" if metric.status == "needs_review" else "METRIC_NOT_APPROVED"
                raise SemanticCompileError(code, f"Metric '{metric.name}' is not approved", {"metric_id": metric.id})
        return metrics

    @staticmethod
    def _require_same_base(definitions: list[MetricDefinition]) -> str:
        bases = {item.metric.base_entity for item in definitions}
        if len(bases) != 1:
            raise SemanticCompileError("INCOMPATIBLE_BASE_ENTITY", "All selected metrics must use the same base entity")
        return bases.pop()

    async def _load_tables(self, db_id: int) -> list[SemanticTableModel]:
        result = await self._db.execute(select(SemanticTableModel).where(SemanticTableModel.db_id == db_id))
        return list(result.scalars().all())

    async def _load_base_columns(self, table_id: int) -> dict[int, str]:
        result = await self._db.execute(select(SemanticColumnModel).where(SemanticColumnModel.table_id == table_id))
        return {column.id: column.column_name for column in result.scalars().all()}

    async def _load_dimensions(self, db_id: int, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        stmt = (
            select(SemanticColumnModel, SemanticTableModel)
            .join(SemanticTableModel, SemanticColumnModel.table_id == SemanticTableModel.id)
            .where(SemanticTableModel.db_id == db_id, SemanticColumnModel.id.in_(ids))
        )
        rows = list((await self._db.execute(stmt)).all())
        by_id = {column.id: _column_info(column, table) for column, table in rows}
        if missing := set(ids) - by_id.keys():
            raise SemanticCompileError("UNKNOWN_REFERENCE", "Columns not found", {"column_ids": sorted(missing)})
        return [by_id[item_id] for item_id in ids]

    async def _load_runtime_filters(self, db_id: int, filters: list[SemanticQueryFilter]) -> list[dict[str, Any]]:
        if not filters:
            return []
        columns = await self._load_dimensions(db_id, [item.column_id for item in filters])
        return [
            {**column, "operator": item.operator, "value": item.value}
            for column, item in zip(columns, filters, strict=True)
        ]

    async def _resolve_joins(
        self,
        db_id: int,
        base: SemanticTableModel,
        dimensions: list[dict[str, Any]],
        tables: dict[int, SemanticTableModel],
    ) -> list[dict[str, Any]]:
        result = await self._db.execute(
            select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == db_id)
        )
        relationships = [item for item in result.scalars().all() if item.validation_status in {"valid", None}]
        column_names = await self._relationship_columns(relationships)
        joins: list[dict[str, str]] = []
        joined = {base.id}
        for table_id in {item["table_id"] for item in dimensions} - joined:
            for relationship in _safe_join_path(relationships, base.id, table_id, tables, column_names):
                target_id = relationship.to_entity_id
                if target_id not in joined:
                    joins.append(
                        {
                            "relationship_id": relationship.id,
                            "table_name": tables[target_id].table_name,
                            "physical_schema": tables[target_id].physical_schema,
                            "condition": _relationship_condition(relationship, column_names),
                        }
                    )
                    joined.add(target_id)
        return joins

    async def _relationship_columns(
        self,
        relationships: list[CanonicalRelationshipModel],
    ) -> dict[int, tuple[str, str]]:
        ids = {
            value
            for relationship in relationships
            for pair in relationship.column_pairs or []
            for value in (pair["from_column_id"], pair["to_column_id"])
        }
        if not ids:
            return {}
        stmt = (
            select(SemanticColumnModel, SemanticTableModel)
            .join(SemanticTableModel, SemanticColumnModel.table_id == SemanticTableModel.id)
            .where(SemanticColumnModel.id.in_(ids))
        )
        return {
            column.id: (table.table_name, column.column_name) for column, table in (await self._db.execute(stmt)).all()
        }

    def _build_query(
        self,
        dialect: str,
        metrics: list[SemanticMetricModel],
        definitions: list[MetricDefinition],
        base: SemanticTableModel,
        base_columns: dict[int, str],
        dimensions: list[dict[str, Any]],
        joins: list[dict[str, Any]],
        runtime_filters: list[dict[str, Any]],
        limit: int,
    ) -> CompiledQuery:
        parameters: dict[str, Any] = {}
        dimensions_sql, group_sql = _dimension_expressions(dimensions, dialect)
        metrics_sql = _metric_expressions(metrics, definitions, base, base_columns, dialect, parameters)
        sql = _assemble_sql(
            dimensions_sql + metrics_sql, base, joins, runtime_filters, group_sql, dialect, parameters, limit
        )
        validate_read_only(sql)
        metadata = _compiled_metadata(base, metrics, dimensions, joins)
        return CompiledQuery(sql=sql, parameters=parameters, metadata=metadata)


def _canonical_definitions(metrics: list[SemanticMetricModel]) -> list[MetricDefinition]:
    definitions = [MetricDefinition.model_validate(item.definition) for item in metrics]
    invalid = (item.schema_version != 2 or item.diagnostics or not item.metric.grain.column_ids for item in definitions)
    if any(invalid):
        raise SemanticCompileError("METRIC_NEEDS_REVIEW", "Metric definition is not canonical v2")
    return definitions


def _apply_time_grains(dimensions: list[dict[str, Any]], selections: list[DimensionSelection]) -> None:
    for dimension, selection in zip(dimensions, selections, strict=True):
        dimension["time_grain"] = selection.time_grain
        if selection.time_grain and not dimension["is_time_dimension"]:
            raise SemanticCompileError(
                "INVALID_TIME_GRAIN",
                f"Column {selection.column_id} is not a time dimension",
                {"column_id": selection.column_id},
            )


def _safe_join_path(
    relationships: list[CanonicalRelationshipModel],
    base_id: int,
    table_id: int,
    tables: dict[int, SemanticTableModel] | None = None,
    column_names: dict[int, tuple[str, str]] | None = None,
) -> list[CanonicalRelationshipModel]:
    paths = _many_to_one_paths(relationships, base_id, table_id)
    if len(paths) > 1:
        if tables and column_names and table_id in tables:
            target_table = tables[table_id].table_name.lower().rstrip("s")

            def _path_score(p: list[CanonicalRelationshipModel]) -> tuple[int, int, int]:
                hop_len = len(p)
                match_name = 0
                if hop_len == 1 and p[0].column_pairs:
                    from_col_id = p[0].column_pairs[0].get("from_column_id")
                    if from_col_id in column_names:
                        col_name = column_names[from_col_id][1].lower()
                        if col_name in {f"{target_table}_id", f"{target_table}id", target_table}:
                            match_name = -1
                return (hop_len, match_name, p[0].id if p else 0)

            ranked = sorted(paths, key=_path_score)
            return ranked[0]
        raise SemanticCompileError("AMBIGUOUS_JOIN_PATH", "Multiple safe join paths exist", {"table_id": table_id})
    if not paths:
        _raise_unreachable(relationships, base_id, table_id)
    return paths[0]


def _dimension_expressions(dimensions: list[dict[str, Any]], dialect: str) -> tuple[list[str], list[str]]:
    group_sql = [_dimension_sql(item, dialect) for item in dimensions]
    select_sql = [
        f"{expression} AS {_quoted(_dimension_alias(item), dialect)}"
        for expression, item in zip(group_sql, dimensions, strict=True)
    ]
    return select_sql, group_sql


def _metric_expressions(
    metrics: list[SemanticMetricModel],
    definitions: list[MetricDefinition],
    base: SemanticTableModel,
    columns: dict[int, str],
    dialect: str,
    parameters: dict[str, Any],
) -> list[str]:
    return [
        _compile_metric(definition, base.table_name, columns, dialect, parameters, f"metric_{metric.id}")
        for metric, definition in zip(metrics, definitions, strict=True)
    ]


def _assemble_sql(
    selections: list[str],
    base: SemanticTableModel,
    joins: list[dict[str, Any]],
    filters: list[dict[str, Any]],
    groups: list[str],
    dialect: str,
    parameters: dict[str, Any],
    limit: int,
) -> str:
    columns_clause = ",\n  ".join(selections)
    parts = [f"SELECT\n  {columns_clause}", f"FROM {_table_sql(base, dialect)}"]
    for join in joins:
        parts.append(_join_sql(join, dialect).strip())
    predicates = _runtime_predicates(filters, dialect, parameters)
    if predicates:
        where_clause = " AND\n  ".join(predicates)
        parts.append(f"WHERE\n  {where_clause}")
    if groups:
        groups_clause = ", ".join(groups)
        parts.append(f"GROUP BY {groups_clause}")
    parts.append(f"LIMIT {limit}")
    return "\n".join(parts)


def _join_sql(join: dict[str, Any], dialect: str) -> str:
    condition = _validated_join_condition(join["condition"], dialect)
    table = _table_name(join["physical_schema"], join["table_name"], dialect)
    return f" JOIN {table} ON {condition}"


def _compiled_metadata(
    base: SemanticTableModel,
    metrics: list[SemanticMetricModel],
    dimensions: list[dict[str, Any]],
    joins: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "base_entity": base.table_name,
        "metrics": {f"metric_{item.id}": item.name for item in metrics},
        "dimensions": {f"dimension_{item['column_id']}": item["business_name"] for item in dimensions},
        "relationship_ids": [item["relationship_id"] for item in joins],
    }


def _column_info(column: SemanticColumnModel, table: SemanticTableModel) -> dict[str, Any]:
    dt = (column.data_type or "").upper()
    is_time = column.is_time_dimension or any(t in dt for t in ("DATE", "TIME", "TIMESTAMP", "DATETIME"))
    return {
        "column_id": column.id,
        "column_name": column.column_name,
        "business_name": column.business_name,
        "is_time_dimension": is_time,
        "table_id": table.id,
        "table_name": table.table_name,
    }


def _many_to_one_paths(
    relationships: list[CanonicalRelationshipModel], start: int, target: int
) -> list[list[CanonicalRelationshipModel]]:
    graph: dict[int, list[CanonicalRelationshipModel]] = {}
    for rel in relationships:
        if rel.relationship_type in {"many_to_one", "many-to-one"}:
            graph.setdefault(rel.from_entity_id, []).append(rel)
    queue: deque[tuple[int, list[CanonicalRelationshipModel], set[int]]] = deque([(start, [], {start})])
    matches: list[list[CanonicalRelationshipModel]] = []
    shortest: int | None = None
    while queue:
        current, path, visited = queue.popleft()
        if current == target:
            shortest = len(path) if shortest is None else shortest
            if len(path) == shortest:
                matches.append(path)
            continue
        if shortest is not None and len(path) >= shortest:
            continue
        for relationship in graph.get(current, []):
            if relationship.to_entity_id not in visited:
                queue.append(
                    (
                        relationship.to_entity_id,
                        [*path, relationship],
                        {*visited, relationship.to_entity_id},
                    )
                )
    return matches


def _raise_unreachable(
    relationships: list[CanonicalRelationshipModel],
    base_id: int,
    target_id: int,
) -> None:
    reverse_paths = _many_to_one_paths(relationships, target_id, base_id)
    if reverse_paths:
        raise SemanticCompileError("UNSAFE_FANOUT", "Dimension requires a one-to-many join", {"table_id": target_id})
    raise SemanticCompileError(
        "UNREACHABLE_DIMENSION", "Dimension is not reachable through a safe path", {"table_id": target_id}
    )


def _relationship_condition(
    relationship: CanonicalRelationshipModel,
    columns: dict[int, tuple[str, str]],
) -> str:
    if relationship.column_pairs:
        predicates = [
            f"{_raw_qualified(columns[pair['from_column_id']])} = {_raw_qualified(columns[pair['to_column_id']])}"
            for pair in relationship.column_pairs
        ]
        return " AND ".join(predicates)
    raise SemanticCompileError(
        "RELATIONSHIP_NEEDS_REVIEW",
        "Relationship does not contain canonical column pairs",
        {"relationship_id": relationship.id},
    )


def _raw_qualified(column: tuple[str, str]) -> str:
    return f"{column[0]}.{column[1]}"


def _quoted(name: str, dialect: str) -> str:
    return exp.to_identifier(name, quoted=True).sql(dialect=dialect)


def _qualified(table: str, column: str, dialect: str) -> str:
    return exp.column(column, table=table, quoted=True).sql(dialect=dialect)


def _table_sql(table: SemanticTableModel, dialect: str) -> str:
    return _table_name(table.physical_schema, table.table_name, dialect)


def _table_name(schema: str | None, table: str, dialect: str) -> str:
    if schema:
        return f"{_quoted(schema, dialect)}.{_quoted(table, dialect)}"
    return _quoted(table, dialect)


def _dimension_sql(item: dict[str, Any], dialect: str) -> str:
    column = _qualified(item["table_name"], item["column_name"], dialect)
    grain = item.get("time_grain")
    if not grain:
        return column
    if dialect == "sqlite":
        formats = {"day": "%Y-%m-%d", "week": "%Y-%W", "month": "%Y-%m", "year": "%Y"}
        if grain == "quarter":
            return f"strftime('%Y', {column}) || '-Q' || ((cast(strftime('%m', {column}) as integer) + 2) / 3)"
        return f"strftime('{formats[grain]}', {column})"
    if dialect == "mysql":
        formats = {"day": "%Y-%m-%d", "week": "%x-%v", "month": "%Y-%m", "year": "%Y"}
        if grain == "quarter":
            return f"CONCAT(YEAR({column}), '-Q', QUARTER({column}))"
        return f"DATE_FORMAT({column}, '{formats[grain]}')"
    return f"DATE_TRUNC('{grain}', {column})"


def _dimension_alias(item: dict[str, Any]) -> str:
    return f"dimension_{item['column_id']}"


def _compile_metric(
    definition: MetricDefinition,
    table: str,
    columns: dict[int, str],
    dialect: str,
    parameters: dict[str, Any],
    alias: str,
) -> str:
    formula = definition.metric.formula
    argument = _compile_argument(formula.expression_ast, table, columns, dialect)
    predicates = [
        _predicate(table, _resolved_filter(item, columns), dialect, parameters, "metric")
        for item in definition.metric.filters
    ]
    condition = " AND ".join(predicates)
    conditional = f"CASE WHEN {condition} THEN {argument if argument != '*' else '1'} END" if condition else argument
    if formula.function == "COUNT_DISTINCT":
        aggregate = f"COUNT(DISTINCT {conditional})"
    else:
        aggregate = f"{formula.function}({conditional})"
    return f"{aggregate} AS {_quoted(alias, dialect)}"


def _resolved_filter(item: MetricFilter, columns: dict[int, str]) -> MetricFilter:
    if item.column_id not in columns:
        raise SemanticCompileError(
            "UNKNOWN_REFERENCE",
            "Metric filter contains an unknown column",
            {"column_id": item.column_id},
        )
    return item.model_copy(update={"field": columns[item.column_id]})


def _compile_argument(
    node: MetricExpressionNode | None,
    table: str,
    columns: dict[int, str],
    dialect: str,
) -> str:
    if node is None:
        raise SemanticCompileError("METRIC_NEEDS_REVIEW", "Metric expression is not resolved")
    if node.kind == "column" and node.column_id in columns:
        return _qualified(table, columns[node.column_id], dialect)
    if node.kind == "literal":
        return str(node.value)
    if node.kind == "neg":
        return f"-({_compile_argument(node.children[0], table, columns, dialect)})"
    left = _compile_argument(node.children[0], table, columns, dialect)
    right = _compile_argument(node.children[1], table, columns, dialect)
    if node.kind == "div":
        return f"(CAST({left} AS DECIMAL) / NULLIF({right}, 0))"
    operators = {"add": "+", "sub": "-", "mul": "*"}
    if node.kind in operators:
        return f"({left} {operators[node.kind]} {right})"
    raise SemanticCompileError("UNKNOWN_REFERENCE", "Metric expression contains an unknown column")


def _validated_join_condition(condition: str, dialect: str) -> str:
    parsed = sqlglot.parse_one(condition, read=dialect)
    allowed = (exp.EQ, exp.Column, exp.Identifier)
    if any(not isinstance(node, allowed) for node in parsed.walk()):
        raise ValueError("Unsafe join condition in semantic metadata")
    for column in parsed.find_all(exp.Column):
        column.set("this", exp.to_identifier(column.name, quoted=True))
        column.set("table", exp.to_identifier(column.table, quoted=True))
    return parsed.sql(dialect=dialect)


def _fixed_predicates(
    definitions: list[MetricDefinition],
    table: str,
    dialect: str,
    parameters: dict[str, Any],
) -> list[str]:
    predicates: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for definition in definitions:
        for item in definition.metric.filters:
            key = (item.field, item.operator, repr(item.value))
            if key not in seen:
                seen.add(key)
                predicates.append(_predicate(table, item, dialect, parameters, "metric"))
    return predicates


def _runtime_predicates(filters: list[dict[str, Any]], dialect: str, parameters: dict[str, Any]) -> list[str]:
    return [
        _predicate(
            item["table_name"],
            MetricFilter(field=item["column_name"], operator=item["operator"], value=item["value"]),
            dialect,
            parameters,
            "runtime",
        )
        for item in filters
    ]


def _predicate(
    table: str,
    item: MetricFilter,
    dialect: str,
    parameters: dict[str, Any],
    prefix: str,
) -> str:
    column = _qualified(table, item.field, dialect)
    if item.operator == "is_null":
        return f"{column} IS NULL"
    if item.operator == "is_not_null":
        return f"{column} IS NOT NULL"
    if item.operator in {"in", "not_in"}:
        names = [_bind(parameters, prefix, value) for value in item.value]
        keyword = "IN" if item.operator == "in" else "NOT IN"
        return f"{column} {keyword} ({', '.join(names)})"
    symbols = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    return f"{column} {symbols[item.operator]} {_bind(parameters, prefix, item.value)}"


def _normalize_value(value: Any) -> Any:
    """Coerce ISO date/datetime strings to date/datetime objects for strict DB drivers."""
    if not isinstance(value, str):
        return value
    val = value.strip()
    if len(val) == 10 and val[4] == "-" and val[7] == "-":
        try:
            return date.fromisoformat(val)
        except ValueError:
            return value
    if len(val) >= 19 and val[4] == "-" and val[7] == "-" and (val[10] in ("T", " ")):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value


def _bind(parameters: dict[str, Any], prefix: str, value: Any) -> str:
    name = f"{prefix}_{len(parameters)}"
    parameters[name] = _normalize_value(value)
    return f":{name}"
