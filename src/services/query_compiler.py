"""Compile approved metric definitions into parameterized read-only SQL."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
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
from src.models.metric_definition import MetricDefinition, MetricFilter
from src.models.schemas import SemanticQueryFilter


@dataclass
class CompiledQuery:
    """Hold compiled SQL, bound values, and observable metadata."""

    sql: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


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
        metric_ids: list[int],
        dimension_ids: list[int],
        filters: list[SemanticQueryFilter] | None = None,
        limit: int = 100,
    ) -> CompiledQuery:
        """Compile semantic selections without accepting SQL from the caller."""
        dialect = await self._load_dialect(connection_id)
        metrics = await self._load_metrics(connection_id, metric_ids)
        definitions = [MetricDefinition.model_validate(item.definition) for item in metrics]
        base_name = self._require_same_base(definitions)
        tables = await self._load_tables(connection_id)
        table_by_id = {table.id: table for table in tables}
        table_by_name = {table.table_name: table for table in tables}
        base = table_by_name.get(base_name)
        if base is None:
            raise ValueError(f"Unknown base entity: {base_name}")
        dimensions = await self._load_dimensions(connection_id, dimension_ids)
        joins = await self._resolve_joins(connection_id, base, dimensions, table_by_id)
        runtime_filters = await self._load_runtime_filters(connection_id, filters or [])
        return self._build_query(dialect, definitions, base, dimensions, joins, runtime_filters, min(limit, 1000))

    async def _load_dialect(self, connection_id: int) -> str:
        record = await self._db.get(SemanticDatabaseModel, connection_id)
        if record is None:
            raise ValueError("Semantic database not found")
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
            raise ValueError(f"Metrics not found: {missing}")
        metrics = [found[item_id] for item_id in ids]
        for metric in metrics:
            if metric.status != "approved" or metric.definition is None:
                raise ValueError(f"Metric '{metric.name}' is not an approved definition")
        return metrics

    @staticmethod
    def _require_same_base(definitions: list[MetricDefinition]) -> str:
        bases = {item.metric.base_entity for item in definitions}
        if len(bases) != 1:
            raise ValueError("All selected metrics must use the same base entity")
        return bases.pop()

    async def _load_tables(self, db_id: int) -> list[SemanticTableModel]:
        result = await self._db.execute(select(SemanticTableModel).where(SemanticTableModel.db_id == db_id))
        return list(result.scalars().all())

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
            raise ValueError(f"Dimensions not found: {missing}")
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
    ) -> list[dict[str, str]]:
        result = await self._db.execute(
            select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == db_id)
        )
        relationships = list(result.scalars().all())
        joins: list[dict[str, str]] = []
        joined = {base.id}
        for table_id in {item["table_id"] for item in dimensions} - joined:
            path = _many_to_one_path(relationships, base.id, table_id)
            if path is None:
                raise ValueError("Dimension is not reachable through a safe many-to-one path")
            for target_id, condition in path:
                if target_id not in joined:
                    joins.append({"table_name": tables[target_id].table_name, "condition": condition})
                    joined.add(target_id)
        return joins

    def _build_query(
        self,
        dialect: str,
        definitions: list[MetricDefinition],
        base: SemanticTableModel,
        dimensions: list[dict[str, Any]],
        joins: list[dict[str, str]],
        runtime_filters: list[dict[str, Any]],
        limit: int,
    ) -> CompiledQuery:
        parameters: dict[str, Any] = {}
        dim_sql = [_qualified(item["table_name"], item["column_name"], dialect) for item in dimensions]
        metric_sql = [_compile_metric(item, base.table_name, dialect) for item in definitions]
        sql = f"SELECT {', '.join(dim_sql + metric_sql)} FROM {_quoted(base.table_name, dialect)}"  # noqa: S608
        for join in joins:
            condition = _validated_join_condition(join["condition"], dialect)
            sql += f" JOIN {_quoted(join['table_name'], dialect)} ON {condition}"
        predicates = _fixed_predicates(definitions, base.table_name, dialect, parameters)
        predicates.extend(_runtime_predicates(runtime_filters, dialect, parameters))
        if predicates:
            sql += f" WHERE {' AND '.join(predicates)}"
        if dim_sql:
            sql += f" GROUP BY {', '.join(dim_sql)}"
        sql += f" LIMIT {limit}"
        validate_read_only(sql)
        return CompiledQuery(sql=sql, parameters=parameters, metadata={"base_entity": base.table_name})


def _column_info(column: SemanticColumnModel, table: SemanticTableModel) -> dict[str, Any]:
    return {
        "column_id": column.id,
        "column_name": column.column_name,
        "table_id": table.id,
        "table_name": table.table_name,
    }


def _many_to_one_path(
    relationships: list[CanonicalRelationshipModel], start: int, target: int
) -> list[tuple[int, str]] | None:
    graph: dict[int, list[tuple[int, str]]] = {}
    for rel in relationships:
        if rel.relationship_type in {"many_to_one", "many-to-one"}:
            graph.setdefault(rel.from_entity_id, []).append((rel.to_entity_id, rel.join_condition))
    queue: deque[tuple[int, list[tuple[int, str]]]] = deque([(start, [])])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        if current == target:
            return path
        for neighbor, condition in graph.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, [*path, (neighbor, condition)]))
    return None


def _quoted(name: str, dialect: str) -> str:
    return exp.to_identifier(name, quoted=True).sql(dialect=dialect)


def _qualified(table: str, column: str, dialect: str) -> str:
    return exp.column(column, table=table, quoted=True).sql(dialect=dialect)


def _compile_metric(definition: MetricDefinition, table: str, dialect: str) -> str:
    formula = definition.metric.formula
    if formula.expression == "*":
        argument = "*"
    else:
        parsed = sqlglot.parse_one(formula.expression)
        for column in parsed.find_all(exp.Column):
            column.set("table", exp.to_identifier(table, quoted=True))
            column.set("this", exp.to_identifier(column.name, quoted=True))
        argument = parsed.sql(dialect=dialect)
    if formula.function == "COUNT_DISTINCT":
        aggregate = f"COUNT(DISTINCT {argument})"
    else:
        aggregate = f"{formula.function}({argument})"
    return f"{aggregate} AS {_quoted(definition.metric.name, dialect)}"


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


def _bind(parameters: dict[str, Any], prefix: str, value: Any) -> str:
    name = f"{prefix}_{len(parameters)}"
    parameters[name] = value
    return f":{name}"
