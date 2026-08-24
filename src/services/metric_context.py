"""Build bounded, relationship-complete schema context for Metric AI."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import CanonicalRelationshipModel, SemanticTableModel
from src.services.llm import get_llm
from src.services.llm_json import ainvoke_json

_SCOPE_PROMPT = """Bạn chọn phạm vi schema cho một KPI. Chỉ trả JSON:
{{"table_names":["..."],"needs_clarification":false,"question":"..."}}
Chỉ chọn bảng có trong inventory. Nếu KPI có nhiều domain hợp lý hoặc inventory không đủ,
đặt needs_clarification=true và viết câu hỏi làm rõ bằng tiếng Việt. Không viết SQL.

Inventory schema:\n{inventory}\n\nKPI: {question}"""

_DATA_SCOPE_PROMPT = """Chọn các bảng schema cần thiết để trả lời câu hỏi khám phá dữ liệu. Chỉ trả JSON:
{{"table_names":["..."],"needs_clarification":false,"question":"..."}}
Chỉ chọn bảng có trong inventory. Chọn đủ bảng liên quan, nhưng không chọn toàn bộ schema.
Nếu câu hỏi chưa đủ rõ, đặt needs_clarification=true và hỏi lại bằng tiếng Việt theo ngôn ngữ nghiệp vụ.
Không viết SQL.

Inventory schema:\n{inventory}\n\nCâu hỏi: {question}"""


@dataclass(frozen=True)
class MetricContextResult:
    """A safe schema subgraph or a user-facing diagnostic."""

    schema: dict[str, Any]
    diagnostic: dict[str, Any]


async def build_metric_context(
    db: AsyncSession, db_id: int, question: str, token_budget: int, target_tables: list[str] | None = None
) -> MetricContextResult:
    """Select and expand a complete semantic context without raw string truncation."""
    tables, relationships = await _load_metadata(db, db_id)
    inventory = _inventory(tables)
    if _token_estimate(inventory) > token_budget:
        return _clarification("Schema quá lớn; hãy nêu rõ domain hoặc bảng cần dùng.")
    selected, diagnostic = await _select_tables(question, inventory, tables, target_tables)
    if diagnostic:
        return MetricContextResult(schema={}, diagnostic=diagnostic)
    schema = _expand_context(tables, relationships, selected)
    if _token_estimate(schema) > token_budget:
        return _clarification("Phạm vi KPI quá rộng; hãy nêu rõ bảng hoặc dimension cần tính.")
    return MetricContextResult(schema=schema, diagnostic=_ready_diagnostic(schema))


async def build_data_context(db: AsyncSession, db_id: int, question: str, token_budget: int) -> MetricContextResult:
    """Build a focused schema context for a non-metric data question."""
    tables, relationships = await _load_metadata(db, db_id)
    if _asks_for_temporal_fields(question):
        return _temporal_context(tables)
    inventory = _inventory(tables)
    if _token_estimate(inventory) > token_budget:
        return _clarification("Schema khá lớn. Bạn muốn xem phần đơn hàng, khách hàng hay sản phẩm?")
    selected, diagnostic = await _select_tables(question, inventory, tables, None, _DATA_SCOPE_PROMPT)
    if diagnostic:
        return MetricContextResult(schema={}, diagnostic=diagnostic)
    schema = _expand_context(tables, relationships, selected)
    if _token_estimate(schema) > token_budget:
        return _clarification("Bạn muốn xem phần dữ liệu nào: đơn hàng, khách hàng hay sản phẩm?")
    return MetricContextResult(schema=schema, diagnostic=_ready_diagnostic(schema))


async def _load_metadata(
    db: AsyncSession, db_id: int
) -> tuple[list[SemanticTableModel], list[CanonicalRelationshipModel]]:
    """Load semantic tables and validated relationship graph from metadata only."""
    table_stmt = (
        select(SemanticTableModel)
        .options(selectinload(SemanticTableModel.columns))
        .where(SemanticTableModel.db_id == db_id)
    )
    relationship_stmt = (
        select(CanonicalRelationshipModel)
        .options(
            selectinload(CanonicalRelationshipModel.from_entity), selectinload(CanonicalRelationshipModel.to_entity)
        )
        .where(
            CanonicalRelationshipModel.connection_id == db_id, CanonicalRelationshipModel.validation_status == "valid"
        )
    )
    tables = list((await db.execute(table_stmt)).scalars().all())
    relationships = list((await db.execute(relationship_stmt)).scalars().all())
    return tables, relationships


def _inventory(tables: list[SemanticTableModel]) -> list[dict[str, Any]]:
    """Create a compact all-table inventory without values or connection details."""
    return [
        {
            "table_name": table.table_name,
            "business_name": table.business_name,
            "description": table.description,
            "columns": [column.column_name for column in table.columns],
        }
        for table in tables
    ]


async def _select_tables(
    question: str,
    inventory: list[dict[str, Any]],
    tables: list[SemanticTableModel],
    target_tables: list[str] | None,
    prompt_template: str = _SCOPE_PROMPT,
) -> tuple[set[str], dict[str, Any] | None]:
    """Use the first controlled AI call to select a business domain."""
    valid = {table.table_name for table in tables}
    if target_tables:
        selected = set(target_tables) & valid
        return (
            (selected, None)
            if selected
            else (set(), _clarification("Bảng được chọn không tồn tại trong schema.").diagnostic)
        )
    prompt = prompt_template.format(inventory=json.dumps(inventory, ensure_ascii=False), question=question)
    payload = await ainvoke_json(get_llm(role="metric"), prompt)
    selected = (
        {str(name) for name in payload.get("table_names", []) if str(name) in valid}
        if isinstance(payload, dict)
        else set()
    )
    if not isinstance(payload, dict) or payload.get("needs_clarification") or not selected:
        message = payload.get("question") if isinstance(payload, dict) else "Hãy nêu rõ phần dữ liệu bạn muốn xem."
        return set(), _clarification(str(message)).diagnostic
    return selected, None


def _asks_for_temporal_fields(question: str) -> bool:
    """Recognize schema-discovery questions about date and time fields."""
    normalized = _strip_accents(question).lower()
    markers = ("thoi gian", "date/time", "date time", "timestamp", "ngay", "thang", "nam")
    return any(marker in normalized for marker in markers)


def _strip_accents(value: str) -> str:
    """Make common Vietnamese schema questions insensitive to diacritics."""
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn").replace("đ", "d")


def _temporal_context(tables: list[SemanticTableModel]) -> MetricContextResult:
    """Return all temporal fields without a scope-selection call."""
    items = [_temporal_table_payload(table) for table in tables]
    schema = {"tables": [item for item in items if item is not None], "relationships": []}
    return MetricContextResult(schema=schema, diagnostic=_ready_diagnostic(schema))


def _temporal_table_payload(table: SemanticTableModel) -> dict[str, Any] | None:
    """Serialize temporal columns from one semantic table."""
    columns = [_column_payload(column) for column in table.columns if _is_temporal_column(column)]
    if not columns:
        return None
    return {
        "table_name": table.table_name,
        "business_name": table.business_name,
        "description": table.description,
        "columns": columns,
    }


def _is_temporal_column(column: Any) -> bool:
    """Identify a SQL date, time, or timestamp column."""
    data_type = (column.data_type or "").upper()
    return any(marker in data_type for marker in ("DATE", "TIME", "TIMESTAMP"))


def _expand_context(
    tables: list[SemanticTableModel], relationships: list[CanonicalRelationshipModel], selected: set[str]
) -> dict[str, Any]:
    """Keep the selected business subgraph without unrelated neighbor tables."""
    included = set(selected)
    return {
        "tables": [_table_payload(table) for table in tables if table.table_name in included],
        "relationships": _relations(relationships, included),
    }


def _table_payload(table: SemanticTableModel) -> dict[str, Any]:
    """Serialize one table without sample values or other data-bearing metadata."""
    return {
        "table_name": table.table_name,
        "business_name": table.business_name,
        "description": table.description,
        "columns": [_column_payload(column) for column in table.columns],
    }


def _column_payload(column: Any) -> dict[str, Any]:
    """Serialize one semantic column without data values."""
    return {
        "column_name": column.column_name,
        "data_type": column.data_type,
        "business_name": column.business_name,
        "description": column.description,
        "is_primary_key": column.is_primary_key,
        "is_foreign_key": column.is_foreign_key,
        "fk_target_table": column.fk_target_table,
        "fk_target_column": column.fk_target_column,
    }


def _relations(relationships: list[CanonicalRelationshipModel], included: set[str]) -> list[dict[str, str]]:
    """Serialize only relationships wholly contained in the selected context."""
    return [
        {
            "from_table": relation.from_entity.table_name,
            "to_table": relation.to_entity.table_name,
            "join_condition": relation.join_condition,
            "relationship_type": relation.relationship_type,
        }
        for relation in relationships
        if relation.from_entity.table_name in included and relation.to_entity.table_name in included
    ]


def _token_estimate(value: Any) -> int:
    """Use a conservative token estimate without provider-specific tokenizers."""
    return (len(json.dumps(value, ensure_ascii=False)) + 3) // 4


def _clarification(message: str) -> MetricContextResult:
    """Return a safe clarification result without calling downstream Metric AI."""
    return MetricContextResult(schema={}, diagnostic={"status": "needs_clarification", "message": message})


def _ready_diagnostic(schema: dict[str, Any]) -> dict[str, Any]:
    """Return non-sensitive context telemetry for authorized Data Leads."""
    return {
        "status": "ready",
        "tables": [item["table_name"] for item in schema["tables"]],
        "relationship_count": len(schema["relationships"]),
    }
