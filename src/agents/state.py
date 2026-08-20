from __future__ import annotations

from typing import Any, TypedDict

from src.models.raw_schema import DatabaseType, RawSchema


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

    user_id: int
    """ID của user đang thực hiện pipeline — cần cho semantic_service."""

    conn_url_enc: str
    """Connection URL đã được Fernet encrypt — không bao giờ plaintext."""

    db_type: DatabaseType
    """Declared target database type: postgresql, mysql, or sqlite."""

    # Flow 1 — Introspect Node output
    raw_schema: RawSchema
    """Schema kỹ thuật thô từ Live Introspection hoặc DDL Dump parsing."""

    introspection_warnings: list[str]
    """Recoverable table-level schema introspection warnings."""

    # Flow 1 — Enrich Node output
    enriched_schema: dict[str, Any]
    """Schema đã được LLM bổ sung business_name + description
    cho từng bảng và từng cột.
    """

    global_glossary: dict[str, Any] | None
    """Pass 1 global table glossary — business_name + description for all tables."""

    # Flow 1 — MetricSuggest Node output
    existing_metrics: list[dict[str, Any]]
    """Tóm tắt các metric đã lưu (từ Metadata Store) dùng để đối chiếu trùng lặp."""

    dedupe_performed: bool
    """True nếu dedupe đã chạy; False khi không tải được existing metrics (lỗi DB)."""

    suggested_metrics: list[dict[str, Any]]
    """Danh sách Business Metrics do LLM đề xuất.
    Mỗi metric là một MetricDefinition JSON, không chứa SQL.
    """

    duplicate_notices: list[dict[str, Any]]
    """Advisory notices: metric đề xuất trùng metric đã lưu (không chặn lưu)."""

    # Flow 1 — HITL Interrupt (user review & edit)
    hitl_approved: bool
    """True nếu BA/DA đã duyệt và xác nhận Semantic Layer."""

    # Flow 1 — Save Node output
    semantic_layer_id: int
    """ID của Semantic Layer đã được lưu vào Metadata Store."""

    # Shared — error handling
    error: str
    """Thông báo lỗi nếu có bất kỳ node nào thất bại."""

    # Chat Orchestrator — Input
    user_message: str
    """Câu hỏi / tin nhắn ngôn ngữ tự nhiên từ người dùng gửi vào chatbot."""

    # Chat Orchestrator — Router output
    intent: str
    """Intent: 'chitchat', 'data_question', 'metric_query', or 'out_of_scope'."""

    can_generate_metrics: bool
    """Server-derived capability controlling metric-authoring routing."""

    approved_metrics: list[dict[str, Any]]
    """Approved metric context available to the read-only data assistant."""

    metric_decision: dict[str, Any]
    """Validated metric availability and schema-support decision for one chat turn."""

    suggestion_action: str
    """Server-derived action for metric suggestions: save or submit for review."""

    context_diagnostic: dict[str, Any]
    """Safe Metric AI context status for the current chat turn."""

    # Chitchat Agent — Output
    chat_response: str
    """Câu trả lời ngôn ngữ tự nhiên khi intent = 'chitchat', 'data_question', hoặc 'out_of_scope'."""

    # Chat persistence — history excludes the current user message.
    session_id: str
    """ID phiên chat hiện tại."""

    chat_history: list[dict[str, str]]
    """Prior user/assistant messages used as conversational context."""
