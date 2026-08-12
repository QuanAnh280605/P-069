from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from src.models.metric_definition import FilterOperator, MetricDefinition
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
    """Create a metric from a canonical definition, never from SQL."""

    definition: MetricDefinition
    source: Literal["ai", "manual"] = "manual"


class MetricUpdate(BaseModel):
    """Replace a metric definition and create a new pending version."""

    definition: MetricDefinition


class MetricResponse(BaseModel):
    """Return a persisted canonical metric definition."""

    metric_id: int
    definition: MetricDefinition | None = None
    source: Literal["ai", "manual"]
    name: str = ""
    description: str = ""
    sql_template: str = ""


class MetricVersionResponse(BaseModel):
    """Response for a single metric version record."""

    id: int
    metric_id: int
    version: int
    definition: MetricDefinition | None = None
    formula: str = ""
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
    """An unsaved metric definition with a server-rendered YAML preview."""

    definition: MetricDefinition
    yaml_preview: str


class CustomMetricGenerateResponse(BaseModel):
    """Response chứa danh sách các gợi ý metric từ prompt tùy biến."""

    suggestions: list[MetricSuggestionItem] = Field(default_factory=list)


class GeneratedMetric(MetricDefinition):
    """Structured metric definition returned by the LLM."""


class MetricSuggestions(BaseModel):
    """Structured output payload từ LLM chứa danh sách 1-3 metric."""

    metrics: list[MetricDefinition] = Field(
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
    semantic_db_id: int | None = None
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
    semantic_db_id: int | None = None
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


class SemanticQueryFilter(BaseModel):
    """Runtime predicate referencing an approved semantic column."""

    column_id: int
    operator: FilterOperator
    value: Any = None


TimeGrain = Literal["day", "week", "month", "quarter", "year"]


class DimensionSelection(BaseModel):
    column_id: int
    time_grain: TimeGrain | None = None


class SemanticQuerySpec(BaseModel):
    metric_ids: list[int] = Field(..., min_length=1)
    dimensions: list[DimensionSelection] = Field(default_factory=list)
    filters: list[SemanticQueryFilter] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=1000)


class SemanticQueryRequest(BaseModel):
    """Request payload for executing a semantic query (Flow 2)."""

    metric_ids: list[int] = Field(..., min_length=1, description="List of approved metric IDs")
    dimensions: list[DimensionSelection] = Field(default_factory=list)
    dimension_ids: list[int] = Field(default_factory=list, description="Deprecated raw dimension IDs")
    filters: list[SemanticQueryFilter] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=1000, description="Max rows to return (default 100, max 1000)")

    @model_validator(mode="after")
    def reject_mixed_dimension_contracts(self) -> SemanticQueryRequest:
        """Reject ambiguous requests using both dimension representations."""
        if self.dimensions and self.dimension_ids:
            raise ValueError("Use either dimensions or dimension_ids, not both")
        return self

    def to_spec(self) -> SemanticQuerySpec:
        """Convert the compatibility request into canonical compiler input."""
        dimensions = self.dimensions or [DimensionSelection(column_id=item) for item in self.dimension_ids]
        return SemanticQuerySpec(
            metric_ids=self.metric_ids,
            dimensions=dimensions,
            filters=self.filters,
            limit=self.limit,
        )


class SemanticQueryResponse(BaseModel):
    """Response from a semantic query execution."""

    sql: str = Field(..., description="Compiled SQL query")
    parameters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list, description="Column names in result")
    rows: list[list[Any]] = Field(default_factory=list, description="Result rows")
    row_count: int = Field(default=0, description="Number of rows returned")


class SemanticQueryCompileResponse(BaseModel):
    """Return a deterministic query preview without executing target data."""

    sql: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Canonical Relationships
# ---------------------------------------------------------------------------


class CanonicalRelationshipResponse(BaseModel):
    """Response for a canonical relationship between two semantic tables."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    connection_id: int
    from_entity_id: int
    to_entity_id: int
    relationship_type: str
    join_condition: str
    created_at: datetime


class SemanticCatalogColumn(BaseModel):
    """Expose a selectable canonical column to semantic query clients."""

    model_config = ConfigDict(from_attributes=True)

    column_id: int
    column_name: str
    business_name: str
    data_type: str
    is_time_dimension: bool = False
    allowed_values: Any = None


class SemanticCatalogTable(BaseModel):
    """Expose one canonical entity and its queryable columns."""

    model_config = ConfigDict(from_attributes=True)

    table_id: int
    table_name: str
    business_name: str
    columns: list[SemanticCatalogColumn] = Field(default_factory=list)


class SemanticCatalogResponse(BaseModel):
    """Describe metadata required by the deterministic query builder."""

    model_config = ConfigDict(from_attributes=True)

    db_id: int
    source_type: Literal["live", "sql_dump"]
    query_supported: bool
    tables: list[SemanticCatalogTable] = Field(default_factory=list)
    relationships: list[CanonicalRelationshipResponse] = Field(default_factory=list)


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
    definition: MetricDefinition | None
    source: str
    version: int
    status: str
    approved_by: int | None = None
    created_at: datetime


class MetricVersionItem(BaseModel):
    """One version entry in a metric's history."""

    version: int
    definition: MetricDefinition | None = None
    changed_by: int | None = None
    change_reason: str = ""
    created_at: datetime


class MetricHistoryResponse(BaseModel):
    """Response containing a metric's version history."""

    metric_id: int
    metric_name: str
    versions: list[MetricVersionItem]
