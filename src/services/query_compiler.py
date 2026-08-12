"""Semantic Query Compiler — compiles approved metrics and dimensions into read-only SQL.

Provides:
  - SemanticQueryCompiler: compiles metrics + dimensions into SQL via semantic metadata.
  - CompiledQuery: dataclass holding compiled SQL, parameters, and metadata.
  - validate_read_only: SQL guardrail ensuring only SELECT statements are allowed.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field

import sqlglot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from src.models.db import (
    CanonicalRelationshipModel,
    SemanticColumnModel,
    SemanticMetricModel,
    SemanticTableModel,
)


@dataclass
class CompiledQuery:
    """Result of compiling metrics and dimensions into SQL."""

    sql: str
    parameters: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# validate_read_only — SQL guardrail
# ---------------------------------------------------------------------------


def validate_read_only(sql: str) -> bool:
    """Validate that SQL is read-only (SELECT only).

    Raises ValueError with a clear message if any rule is violated:
    - Root AST node must be Select
    - No multi-statement (semicolon-separated)
    - No SELECT ... INTO ...
    - No CTEs containing DML
    - No INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE
    """
    _check_multi_statement(sql)
    parsed = _parse_sql(sql)
    _check_root_is_select(parsed)
    _check_no_select_into(parsed)
    _check_no_cte_dml(parsed)
    _check_no_forbidden_nodes(parsed)
    return True


def _check_multi_statement(sql: str) -> None:
    """Reject semicolon-separated multi-statement queries."""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise ValueError("Multi-statement queries are not allowed")


def _parse_sql(sql: str) -> exp.Expression:
    """Parse SQL into an AST; raise ValueError on parse failure."""
    try:
        return sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"Invalid SQL: {exc}") from exc


def _check_root_is_select(parsed: exp.Expression) -> None:
    """Reject anything that is not a top-level SELECT."""
    if not isinstance(parsed, exp.Select):
        raise ValueError(f"Only SELECT statements are allowed, got {type(parsed).__name__}")


def _check_no_select_into(parsed: exp.Expression) -> None:
    """Reject SELECT ... INTO ..."""
    if parsed.find(exp.Into):
        raise ValueError("SELECT ... INTO is not allowed")


def _check_no_cte_dml(parsed: exp.Expression) -> None:
    """Reject CTEs whose body is INSERT / UPDATE / DELETE."""
    with_block = parsed.find(exp.With)
    if with_block is None:
        return
    for cte in with_block.find_all(exp.CTE):
        cte_body = cte.this
        if isinstance(cte_body, (exp.Insert, exp.Update, exp.Delete)):
            raise ValueError("CTE containing DML (INSERT/UPDATE/DELETE) is not allowed")


def _check_no_forbidden_nodes(parsed: exp.Expression) -> None:
    """Walk the AST and reject any INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE."""
    for node in parsed.walk(bfs=False):
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete)):
            raise ValueError(f"Statement containing {type(node).__name__} is not allowed")
        if isinstance(node, exp.Drop):
            raise ValueError("DROP statement is not allowed")
        if isinstance(node, exp.Alter):
            raise ValueError("ALTER statement is not allowed")
        if isinstance(node, exp.TruncateTable):
            raise ValueError("TRUNCATE statement is not allowed")


# ---------------------------------------------------------------------------
# SemanticQueryCompiler
# ---------------------------------------------------------------------------

_FORMULA_RE = re.compile(r"(\w+)\(\s*(?:DISTINCT\s+)?(?:(\w+)\.)?(\w+|\*)\s*\)", re.IGNORECASE)


class SemanticQueryCompiler:
    """Compiles approved metrics and dimensions into read-only SQL."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compile(
        self,
        connection_id: int,
        metric_ids: list[int],
        dimension_ids: list[int],
        filters: str | None = None,
        limit: int = 100,
    ) -> CompiledQuery:
        """Compile metrics and dimensions into a SQL query.

        Args:
            connection_id: Semantic database ID.
            metric_ids: List of metric IDs (must be status='approved').
            dimension_ids: List of column IDs for GROUP BY dimensions.
            filters: Optional WHERE clause (without the WHERE keyword).
            limit: Maximum rows to return (default 100, max 1000).

        Returns:
            CompiledQuery with sql, parameters, and metadata.

        Raises:
            ValueError: If metrics not approved, dimensions not found, or no join path.
        """
        limit = min(limit, 1000)
        metrics = await self._fetch_approved_metrics(metric_ids)
        dimensions = await self._fetch_dimensions(dimension_ids)
        all_tables = await self._fetch_tables(connection_id)
        table_by_name = {t.table_name: t for t in all_tables}
        table_by_id = {t.id: t for t in all_tables}

        parsed_metrics = [self._parse_formula(m, table_by_name, table_by_id) for m in metrics]
        base_table = table_by_id[metrics[0].base_entity_id]

        joins, tables_used = await self._resolve_joins(
            connection_id, base_table, parsed_metrics, dimensions, table_by_id
        )
        sql = self._build_sql(base_table, dimensions, parsed_metrics, joins, filters, limit)
        validate_read_only(sql)

        return CompiledQuery(
            sql=sql,
            parameters={},
            metadata={
                "tables": [table_by_id[tid].table_name for tid in tables_used],
                "joins": joins,
                "metrics": [m.name for m in metrics],
                "dimensions": [f"{d['table_name']}.{d['column_name']}" for d in dimensions],
            },
        )

    # ------------------------------------------------------------------
    # Data fetching helpers
    # ------------------------------------------------------------------

    async def _fetch_approved_metrics(self, metric_ids: list[int]) -> list[SemanticMetricModel]:
        """Fetch metrics by IDs, raise if any missing or not approved."""
        stmt = select(SemanticMetricModel).where(SemanticMetricModel.id.in_(metric_ids))
        result = await self._db.execute(stmt)
        metrics = list(result.scalars().all())

        if len(metrics) != len(metric_ids):
            found = {m.id for m in metrics}
            raise ValueError(f"Metrics not found: {set(metric_ids) - found}")

        for m in metrics:
            if m.status != "approved":
                raise ValueError(f"Metric '{m.name}' (id={m.id}) is not approved (status={m.status})")
        return metrics

    async def _fetch_dimensions(self, dimension_ids: list[int]) -> list[dict[str, object]]:
        """Fetch dimension columns with their parent table info."""
        stmt = (
            select(SemanticColumnModel, SemanticTableModel)
            .join(
                SemanticTableModel,
                SemanticColumnModel.table_id == SemanticTableModel.id,
            )
            .where(SemanticColumnModel.id.in_(dimension_ids))
        )
        result = await self._db.execute(stmt)
        rows = list(result.all())

        if len(rows) != len(dimension_ids):
            found = {c.id for c, _ in rows}
            raise ValueError(f"Dimension columns not found: {set(dimension_ids) - found}")

        return [
            {
                "column_id": col.id,
                "table_id": tbl.id,
                "table_name": tbl.table_name,
                "column_name": col.column_name,
            }
            for col, tbl in rows
        ]

    async def _fetch_tables(self, connection_id: int) -> list[SemanticTableModel]:
        """Fetch all semantic tables for a connection."""
        stmt = select(SemanticTableModel).where(SemanticTableModel.db_id == connection_id)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Formula parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_formula(
        metric: SemanticMetricModel,
        table_by_name: dict[str, SemanticTableModel],
        table_by_id: dict[int, SemanticTableModel],
    ) -> dict[str, object]:
        """Parse metric formula to extract aggregation, table, and column.

        Formula formats:
            SUM(orders.total_amount)
            COUNT(DISTINCT orders.customer_id)
            COUNT(*)
            AVG(price)  — no table prefix, resolve via base_entity_id
        """
        formula = metric.formula or metric.sql_template or ""
        match = _FORMULA_RE.match(formula.strip())

        if not match:
            tbl = table_by_id.get(metric.base_entity_id)
            return {
                "aggregation": metric.aggregation_type or "COUNT",
                "distinct": False,
                "table_id": metric.base_entity_id,
                "table_name": tbl.table_name if tbl else "",
                "column": "*",
            }

        aggregation = match.group(1).upper()
        raw_table_name = match.group(2)
        column = match.group(3)
        distinct = "distinct" in formula.lower()

        if raw_table_name:
            table = table_by_name.get(raw_table_name)
            return {
                "aggregation": aggregation,
                "distinct": distinct,
                "table_id": table.id if table else None,
                "table_name": table.table_name if table else raw_table_name,
                "column": column,
            }

        table = table_by_id.get(metric.base_entity_id)
        return {
            "aggregation": aggregation,
            "distinct": distinct,
            "table_id": metric.base_entity_id,
            "table_name": table.table_name if table else "",
            "column": column,
        }

    # ------------------------------------------------------------------
    # Join resolution (BFS)
    # ------------------------------------------------------------------

    async def _resolve_joins(
        self,
        connection_id: int,
        base_table: SemanticTableModel,
        parsed_metrics: list[dict],
        dimensions: list[dict],
        table_by_id: dict[int, SemanticTableModel],
    ) -> tuple[list[dict[str, str]], set[int]]:
        """Resolve join clauses needed to connect all required tables.

        Returns (joins, tables_used) where each join dict has
        'table_name' and 'condition'.
        """
        tables_needed: set[int] = {base_table.id}
        for pm in parsed_metrics:
            if pm["table_id"]:
                tables_needed.add(pm["table_id"])
        for dim in dimensions:
            tables_needed.add(dim["table_id"])

        relationships = await self._fetch_relationships(connection_id)

        joins: list[dict[str, str]] = []
        tables_used: set[int] = {base_table.id}

        for table_id in tables_needed:
            if table_id == base_table.id:
                continue
            path = self._find_join_path(relationships, base_table.id, table_id)
            if path is None:
                target = table_by_id.get(table_id)
                target_name = target.table_name if target else str(table_id)
                raise ValueError(f"Cannot join tables: no path from {base_table.table_name} to {target_name}")
            for join_table_id, condition in path:
                if join_table_id not in tables_used:
                    joins.append(
                        {
                            "table_name": table_by_id[join_table_id].table_name,
                            "condition": condition,
                        }
                    )
                    tables_used.add(join_table_id)

        return joins, tables_used

    async def _fetch_relationships(self, connection_id: int) -> list[CanonicalRelationshipModel]:
        """Fetch all canonical relationships for a connection."""
        stmt = select(CanonicalRelationshipModel).where(CanonicalRelationshipModel.connection_id == connection_id)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _find_join_path(
        relationships: list[CanonicalRelationshipModel],
        from_table_id: int,
        to_table_id: int,
    ) -> list[tuple[int, str]] | None:
        """BFS to find the shortest join path between two tables.

        Returns a list of (table_id, join_condition) pairs, or None if
        no path exists.
        """
        graph: dict[int, list[tuple[int, str]]] = {}
        for rel in relationships:
            graph.setdefault(rel.from_entity_id, []).append((rel.to_entity_id, rel.join_condition))
            graph.setdefault(rel.to_entity_id, []).append((rel.from_entity_id, rel.join_condition))

        queue: deque[tuple[int, list[tuple[int, str]]]] = deque([(from_table_id, [])])
        visited: set[int] = {from_table_id}

        while queue:
            node, path = queue.popleft()
            if node == to_table_id:
                return path
            for neighbor, condition in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [(neighbor, condition)]))

        return None

    # ------------------------------------------------------------------
    # SQL generation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sql(
        base_table: SemanticTableModel,
        dimensions: list[dict],
        parsed_metrics: list[dict],
        joins: list[dict[str, str]],
        filters: str | None,
        limit: int,
    ) -> str:
        """Build the final SQL string from resolved components."""
        dim_exprs = [f"{d['table_name']}.{d['column_name']}" for d in dimensions]
        metric_exprs = []
        for pm in parsed_metrics:
            distinct = "DISTINCT " if pm["distinct"] else ""
            metric_exprs.append(f"{pm['aggregation']}({distinct}{pm['table_name']}.{pm['column']})")

        select_clause = ", ".join(dim_exprs + metric_exprs)
        sql = f"SELECT {select_clause} FROM {base_table.table_name}"  # noqa: S608
        for j in joins:
            sql += f" JOIN {j['table_name']} ON {j['condition']}"
        if filters:
            sql += f" WHERE {filters}"
        sql += f" GROUP BY {', '.join(dim_exprs)}"
        sql += f" LIMIT {limit}"
        return sql
