from __future__ import annotations

from typing import Any, Literal, TypedDict

from src.models.schema_metadata import (
    ParseCompleteness,
    ParseDiagnostic,
    RawSchemaMetadata,
    SchemaDialect,
)


class AgentState(TypedDict, total=False):
    """State schema cho LangGraph Flow 1 pipeline.

    Fields được populate theo thứ tự node:
    1. Introspect Node  → raw_schema
    2. Enrich Node      → enriched_schema
    3. MetricSuggest    → suggested_metrics
    4. HITL Interrupt   → reviewed (chờ user approve)
    5. Save Node        → semantic_layer_id
    """

    # Input
    db_id: int
    """ID của semantic_databases record trong Metadata Store."""

    conn_url_enc: str
    """Connection URL đã được Fernet encrypt — không bao giờ plaintext."""

    # Flow 1 — Introspect Node output
    source_mode: Literal["live", "dump"]
    """Acquisition adapter used to produce canonical metadata."""

    dialect: SchemaDialect
    """SQL dialect attached to canonical metadata."""

    raw_schema: RawSchemaMetadata
    """Canonical technical metadata shared by Inspector and dump adapters."""

    diagnostics: tuple[ParseDiagnostic, ...]
    """Safe acquisition diagnostics, kept outside raw_schema."""

    parse_completeness: ParseCompleteness
    """Whether the adapter proved completeness of supported core metadata."""

    # Flow 1 — Enrich Node output
    enriched_schema: dict[str, Any]
    """Schema đã được LLM bổ sung business_name + description
    cho từng bảng và từng cột.
    """

    # Flow 1 — MetricSuggest Node output
    suggested_metrics: list[dict[str, Any]]
    """Danh sách Business Metrics do LLM đề xuất.
    Mỗi metric gồm: name, description, sql_template.
    """

    # Flow 1 — HITL Interrupt (user review & edit)
    hitl_approved: bool
    """True nếu BA/DA đã duyệt và xác nhận Semantic Layer."""

    # Flow 1 — Save Node output
    semantic_layer_id: int
    """ID của Semantic Layer đã được lưu vào Metadata Store."""

    # Shared — error handling
    error: str
    """Thông báo lỗi nếu có bất kỳ node nào thất bại."""
