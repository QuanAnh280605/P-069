from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.models.raw_schema import RawSchema
from src.models.schema_metadata import ParseDiagnostic, RawSchemaMetadata, SchemaDialect

# ---------------------------------------------------------------------------
# User Authentication & RBAC Schemas
# ---------------------------------------------------------------------------


class UserRegisterRequest(BaseModel):
    """Request payload cho đăng ký tài khoản người dùng mới."""

    email: EmailStr = Field(..., description="Email đăng nhập độc nhất")
    username: str = Field(..., min_length=3, max_length=50, description="Tên tài khoản (username)")
    password: str = Field(..., min_length=8, max_length=100, description="Mật khẩu (tối thiểu 8 ký tự)")
    full_name: str = Field(default="", max_length=200, description="Họ và tên hiển thị")


class UserLoginRequest(BaseModel):
    """Request payload cho đăng nhập người dùng."""

    email_or_username: str = Field(..., min_length=1, description="Email hoặc Tên tài khoản")
    password: str = Field(..., min_length=1, description="Mật khẩu người dùng")


class GoogleAuthRequest(BaseModel):
    """Request payload cho đăng nhập/đăng ký bằng Google OAuth ID token."""

    credential: str = Field(..., description="Google ID Token từ Client-side OAuth")


class RefreshTokenRequest(BaseModel):
    """Request payload cho refresh JWT token."""

    refresh_token: str = Field(..., min_length=1, description="JWT Refresh Token")


class TokenResponse(BaseModel):
    """Response trả về Access Token và Refresh Token JWT."""

    access_token: str = Field(..., description="JWT Access Token")
    refresh_token: str = Field(..., description="JWT Refresh Token")
    token_type: str = Field(default="bearer", description="Loại token")
    expires_in: int = Field(..., description="Thời gian hết hạn Access Token (giây)")


class UserProfileResponse(BaseModel):
    """Thông tin hồ sơ người dùng trả về."""

    id: int
    email: str
    username: str
    full_name: str
    role: Literal["admin", "analyst"]
    status: Literal["active", "inactive", "suspended"]
    created_at: datetime


# ---------------------------------------------------------------------------
# DB Connection
# ---------------------------------------------------------------------------


class DBConnectionRequest(BaseModel):
    """Request body để kết nối Target DB và kick-off Flow 1."""

    display_name: str = Field(..., min_length=1, max_length=200, description="Tên gợi nhớ của DB")
    db_type: Literal["postgresql", "mysql", "sqlite"] = Field(..., description="Loại Target DB")
    conn_url: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Connection URL — sẽ được Fernet encrypt trước khi lưu",
    )


class DBConnectionResponse(BaseModel):
    """Response sau khi kết nối thành công và bắt đầu introspect."""

    db_id: int = Field(..., description="ID của DB record trong Metadata Store")
    message: str = Field(default="Introspection started")


# ---------------------------------------------------------------------------
# Semantic Layer — Table & Column
# ---------------------------------------------------------------------------


class SemanticTableUpdate(BaseModel):
    """Cập nhật business_name / description cho một bảng (HITL inline edit)."""

    business_name: str = Field(..., min_length=1, max_length=200, description="Tên nghiệp vụ tiếng Việt")
    description: str = Field(default="", max_length=1000, description="Mô tả chi tiết")


class SemanticColumnUpdate(BaseModel):
    """Cập nhật business_name / description cho một cột (HITL inline edit)."""

    business_name: str = Field(..., min_length=1, max_length=200, description="Tên nghiệp vụ tiếng Việt")
    description: str = Field(default="", max_length=1000, description="Mô tả chi tiết")


# ---------------------------------------------------------------------------
# Business Metrics
# ---------------------------------------------------------------------------


class MetricCreate(BaseModel):
    """Tạo Business Metric mới (thủ công hoặc từ AI suggestion)."""

    name: str = Field(..., min_length=1, max_length=200, description="Tên chỉ số kinh doanh")
    description: str = Field(..., min_length=1, max_length=1000, description="Mô tả nghiệp vụ")
    sql_template: str = Field(..., min_length=1, description="SQL template tham chiếu (SELECT only)")
    source: Literal["ai", "manual"] = Field(default="manual", description="Nguồn gốc metric")
    formula: str = Field(default="", description="Công thức metric (e.g. SUM(orders.total))")
    aggregation_type: str | None = Field(default=None, description="Kiểu aggregation: SUM, COUNT, AVG, etc.")


class MetricUpdate(BaseModel):
    """Cập nhật một Business Metric đã có."""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    sql_template: str | None = Field(default=None)


class MetricResponse(BaseModel):
    """Response trả về cho một Business Metric."""

    metric_id: int
    name: str
    description: str
    sql_template: str
    source: Literal["ai", "manual"]


class MetricVersionResponse(BaseModel):
    """Response for a single metric version record."""

    id: int
    metric_id: int
    version: int
    formula: str
    changed_by: int | None = None
    change_reason: str = ""
    created_at: datetime


class MetricWithHistoryResponse(MetricResponse):
    """Extended MetricResponse with version, status, approved_by, and version history."""

    version: int
    status: str
    approved_by: int | None = None
    history: list[MetricVersionResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Custom Prompt Metric Generation
# ---------------------------------------------------------------------------


class CustomMetricGenerateRequest(BaseModel):
    """Request payload cho sinh Business Metric theo prompt tùy biến."""

    prompt: str = Field(..., min_length=1, max_length=2000, description="Yêu cầu nghiệp vụ để sinh chỉ số")
    target_tables: list[str] | None = Field(default=None, description="Danh sách bảng giới hạn phạm vi")


class MetricSuggestionItem(BaseModel):
    """Một đề xuất Business Metric do AI sinh (chưa lưu vào DB)."""

    name: str = Field(..., min_length=1, max_length=200, description="Tên chỉ số bằng tiếng Việt")
    description: str = Field(..., min_length=1, max_length=1000, description="Mô tả chỉ số bằng tiếng Việt")
    sql_template: str = Field(..., min_length=1, description="Đúng một câu lệnh SELECT duy nhất")
    source: Literal["ai"] = Field(default="ai", description="Nguồn gợi ý")
    target_table: str | None = Field(default=None, description="Tên bảng chính")
    measure_type: str | None = Field(default=None, description="Hàm tổng hợp: SUM, COUNT, AVG, MIN, MAX...")
    target_column: str | None = Field(default=None, description="Tên cột tính toán chính")
    filter_condition: str | None = Field(default=None, description="Mô tả hoặc mệnh đề lọc WHERE")


class CustomMetricGenerateResponse(BaseModel):
    """Response chứa danh sách các gợi ý metric từ prompt tùy biến."""

    suggestions: list[MetricSuggestionItem] = Field(default_factory=list)


class GeneratedMetric(BaseModel):
    """Structured output item từ LLM cho một metric."""

    name: str = Field(..., description="Tên chỉ số nghiệp vụ bằng tiếng Việt")
    description: str = Field(..., description="Mô tả chi tiết ý nghĩa nghiệp vụ bằng tiếng Việt")
    sql_template: str = Field(..., description="Đúng một câu lệnh SELECT chuẩn SQL")
    target_table: str | None = Field(default=None, description="Tên bảng chính trong SQL")
    measure_type: str | None = Field(default=None, description="Phép tổng hợp SUM, COUNT, AVG...")
    target_column: str | None = Field(default=None, description="Tên cột tính toán")
    filter_condition: str | None = Field(default=None, description="Điều kiện lọc WHERE nếu có")


class MetricSuggestions(BaseModel):
    """Structured output payload từ LLM chứa danh sách 1-3 metric."""

    metrics: list[GeneratedMetric] = Field(
        default_factory=list, description="Danh sách từ 1 đến 3 chỉ số nghiệp vụ liên quan"
    )


# ---------------------------------------------------------------------------
# Semantic Layer — Generate & Review
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Request kick-off Flow 1 pipeline cho một DB đã kết nối."""

    db_id: int = Field(..., description="ID DB đã có trong Metadata Store")


class GenerateResponse(BaseModel):
    """Response sau khi Flow 1 hoàn tất (trạng thái draft, chờ HITL)."""

    db_id: int
    status: Literal["draft", "pending_review", "saved"] = "draft"
    raw_schema: RawSchema
    enriched_schema: dict[str, Any] = Field(default_factory=dict)
    suggested_metrics: list[dict[str, Any]] = Field(default_factory=list)
    canonical_tables: list[dict[str, Any]] = Field(default_factory=list)
    canonical_relationships: list[CanonicalRelationshipResponse] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    """BA/DA xác nhận duyệt và lưu chính thức Semantic Layer."""

    db_id: int = Field(..., description="ID DB cần lưu")


class ApproveResponse(BaseModel):
    """Response sau khi HITL approve và Save Node hoàn tất."""

    semantic_layer_id: int
    message: str = "Semantic Layer saved successfully"


class SqlDumpPreviewResponse(BaseModel):
    """Technical schema metadata parsed from a SQL dump."""

    dialect: SchemaDialect
    raw_schema: RawSchemaMetadata
    diagnostics: tuple[ParseDiagnostic, ...] = ()


class ImportedSchemaCreateRequest(BaseModel):
    """Request to persist parsed technical schema metadata."""

    display_name: str = Field(min_length=1, max_length=200)
    raw_schema: RawSchemaMetadata

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        """Trim and reject an empty display name."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name cannot be empty")
        return normalized


class ImportedSchemaSummaryResponse(BaseModel):
    """List item for one persisted SQL dump schema."""

    id: int
    display_name: str
    dialect: SchemaDialect
    table_count: int
    created_at: datetime
    updated_at: datetime


class ImportedSchemaResponse(ImportedSchemaSummaryResponse):
    """Full persisted SQL dump schema metadata."""

    raw_schema: RawSchemaMetadata


# ---------------------------------------------------------------------------
# Live Target DB Schemas
# ---------------------------------------------------------------------------


class LiveDbConnectRequest(BaseModel):
    """Request payload to connect and introspect a live target database."""

    display_name: str = Field(..., min_length=1, max_length=200)
    dialect: str | None = Field(default="auto", description="Schema dialect or 'auto' for auto-detection")
    conn_url: str = Field(..., min_length=5, max_length=500)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        """Trim and reject empty display name."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name cannot be empty")
        return normalized


class LiveDbSummaryResponse(BaseModel):
    """Summary representation of a persisted live target database connection."""

    id: int
    display_name: str
    dialect: SchemaDialect
    table_count: int
    created_at: datetime
    updated_at: datetime


class LiveDbResponse(LiveDbSummaryResponse):
    """Full representation of a persisted live target database including raw schema."""

    raw_schema: RawSchemaMetadata


# ---------------------------------------------------------------------------
# Semantic Query (Flow 2 — Live DB Only)
# ---------------------------------------------------------------------------


class SemanticQueryRequest(BaseModel):
    """Request payload for executing a semantic query (Flow 2)."""

    metric_ids: list[int] = Field(..., min_length=1, description="List of approved metric IDs")
    dimension_ids: list[int] = Field(default_factory=list, description="List of column IDs for GROUP BY dimensions")
    filters: list[dict[str, Any]] | None = Field(
        default=None, description="Filters (format: {column, operator, value})"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max rows to return (default 100, max 1000)")


class SemanticQueryResponse(BaseModel):
    """Response from a semantic query execution."""

    sql: str = Field(..., description="Compiled SQL query")
    columns: list[str] = Field(default_factory=list, description="Column names in result")
    rows: list[list[Any]] = Field(default_factory=list, description="Result rows")
    row_count: int = Field(default=0, description="Number of rows returned")


# ---------------------------------------------------------------------------
# Canonical Relationships
# ---------------------------------------------------------------------------


class CanonicalRelationshipResponse(BaseModel):
    """Response for a canonical relationship between two semantic tables."""

    id: int
    connection_id: int
    from_entity_id: int
    to_entity_id: int
    relationship_type: str
    join_condition: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Canonical Semantic Layer — Generate, Approve, Metrics List, History
# ---------------------------------------------------------------------------


class SemanticGenerateV2Response(BaseModel):
    """Response after re-running AI enrichment (POST /semantic/generate)."""

    db_id: int
    status: str = "draft"
    tables: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class SemanticApproveV2Response(BaseModel):
    """Response after approving all metrics in a semantic database."""

    db_id: int
    approved_count: int
    message: str = "Metrics approved successfully"


class MetricListItem(BaseModel):
    """A metric with version, status, and approval info."""

    metric_id: int
    name: str
    description: str
    sql_template: str
    source: str
    version: int
    status: str
    approved_by: int | None = None
    created_at: datetime


class MetricVersionItem(BaseModel):
    """One version entry in a metric's history."""

    version: int
    formula: str
    changed_by: int | None = None
    change_reason: str = ""
    created_at: datetime


class MetricHistoryResponse(BaseModel):
    """Response containing a metric's version history."""

    metric_id: int
    metric_name: str
    versions: list[MetricVersionItem]
