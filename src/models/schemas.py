from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator

from src.models.metric_definition import FilterOperator, MetricDefinition, MetricStatus
from src.models.raw_schema import RawSchema
from src.models.schema_metadata import ParseDiagnostic, RawSchemaMetadata, SchemaDialect

WorkspaceRole = Literal["admin", "data_lead", "member"]

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

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    full_name: str
    status: Literal["active", "inactive", "suspended"]
    created_at: datetime


class OrganizationCreateRequest(BaseModel):
    """Request to create a company Workspace."""

    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=120)


class OrganizationSummaryResponse(BaseModel):
    """Workspace summary and current user's role."""

    id: int
    name: str
    slug: str
    role: WorkspaceRole
    permissions: dict[str, bool] = Field(default_factory=dict)
    created_at: datetime


class OrganizationMemberResponse(BaseModel):
    """Workspace member with account identity and role."""

    user_id: int
    email: str
    username: str
    full_name: str
    role: WorkspaceRole
    joined_at: datetime


class OrganizationRoleUpdateRequest(BaseModel):
    """Request to change a Workspace member role."""

    role: WorkspaceRole


class OrganizationInviteCreateRequest(BaseModel):
    """Request to create a one-time Workspace invitation."""

    role: Literal["admin", "data_lead", "member"] = "member"


class OrganizationInviteResponse(BaseModel):
    """Invitation details; raw token is only returned on creation."""

    id: int
    org_id: int
    role: Literal["admin", "data_lead", "member"]
    status: Literal["pending", "accepted", "revoked", "expired"]
    expires_at: datetime
    invite_url: str | None = None


class OrganizationInvitePreviewResponse(BaseModel):
    """Public invitation preview before authentication."""

    organization_name: str
    organization_slug: str
    role: Literal["admin", "data_lead", "member"]
    expires_at: datetime


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
    source: Literal["ai", "manual", "auto_sync"] = "manual"


class MetricUpdate(BaseModel):
    """Replace a metric definition and create a new pending version."""

    definition: MetricDefinition
    change_reason: str = Field(default="", description="Lý do thay đổi (audit log)")


class MetricResponse(BaseModel):
    """Return a persisted canonical metric definition."""

    metric_id: int
    definition: MetricDefinition | None = None
    source: Literal["ai", "manual", "auto_sync"]
    status: MetricStatus = "pending_approval"
    is_deleted: bool = False
    name: str = ""
    description: str = ""
    sql_template: str = ""


class MetricVersionResponse(BaseModel):
    """Response for a single metric version record."""

    id: int
    metric_id: int
    version: int
    name: str = ""
    definition: MetricDefinition | None = None
    formula: str = ""
    status: str = "superseded"
    parent_version: int | None = None
    changed_by: int | None = None
    changed_by_name: str = ""
    change_reason: str = ""
    approved_by: int | None = None
    approved_by_name: str = ""
    approved_at: datetime | None = None
    created_at: datetime


class MetricWithHistoryResponse(MetricResponse):
    """Extended MetricResponse with version, status, approved_by, and version history."""

    version: int
    status: str
    approved_by: int | None = None
    history: list[MetricVersionResponse] = Field(default_factory=list)
    pending_version: MetricVersionResponse | None = Field(
        default=None,
        description="Bản sửa đang chờ duyệt (copy-on-write) — definition đang publish không bị ghi đè",
    )


class MetricUpdateResponse(MetricResponse):
    """Result of editing a metric.

    A published metric is never overwritten: the live definition is returned
    unchanged and the edit is surfaced in ``pending_version`` so the caller can
    tell the reviewer their change is queued instead of applied.
    """

    version: int = 0
    pending_version: MetricVersionResponse | None = Field(
        default=None,
        description="Bản sửa copy-on-write đang chờ duyệt; null nghĩa là bản sửa đã áp dụng trực tiếp",
    )


class MetricRequestCreate(BaseModel):
    """Select one AI suggestion from an owned assistant chat message."""

    assistant_message_id: str = Field(..., min_length=36, max_length=36)
    suggestion_index: int = Field(..., ge=0)


class MetricRequestReview(BaseModel):
    """Data Lead decision for a pending metric request."""

    definition: MetricDefinition | None = None
    review_note: str | None = Field(default=None, max_length=2000)


class MetricRequestResponse(BaseModel):
    """Safe representation of a Member metric request."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    db_id: int
    requester_id: int
    assistant_message_id: str
    suggestion_index: int
    definition: MetricDefinition
    status: Literal["pending", "approved", "rejected"]
    reviewed_by: int | None = None
    review_note: str | None = None
    metric_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NotificationResponse(BaseModel):
    """Persistent in-app notification returned to its recipient."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str
    metric_request_id: int | None = None
    read_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Notification list plus its unread badge count."""

    items: list[NotificationResponse] = Field(default_factory=list)
    unread_count: int = 0


# ---------------------------------------------------------------------------
# Custom Prompt Metric Generation
# ---------------------------------------------------------------------------


class CustomMetricGenerateRequest(BaseModel):
    """Request payload cho sinh Business Metric theo prompt tùy biến."""

    prompt: str = Field(..., min_length=1, max_length=2000, description="Yêu cầu nghiệp vụ để sinh chỉ số")
    target_tables: list[str] | None = Field(default=None, description="Danh sách bảng giới hạn phạm vi")


class MetricConflictInfo(BaseModel):
    """Clarify request: same name as an existing metric but different formula."""

    proposed_metric_name: str  # join key với suggestion (so tên sau normalize)
    existing_metric_id: int | None = None
    existing_metric_name: str
    existing_metric_status: str | None = None
    suggested_name: str = ""
    clarify_question: str = ""


class MetricSuggestionItem(BaseModel):
    """An unsaved metric definition with a server-rendered YAML preview."""

    definition: MetricDefinition
    yaml_preview: str
    conflict: MetricConflictInfo | None = None


class DuplicateMetricNotice(BaseModel):
    """Advisory notice: a proposed metric duplicates an existing saved metric."""

    # Join key với suggestion (so tên sau normalize) — dùng để loại bỏ đề xuất bị flag trùng.
    proposed_metric_name: str | None = None
    existing_metric_id: int | None = None
    existing_metric_name: str
    existing_metric_status: str | None = None
    user_message: str
    similarity_reason: str = ""
    # Read-only preview of the saved metric — attached from DB truth by merge_dedupe.
    existing_definition: MetricDefinition | None = None
    existing_yaml: str = ""


class MetricSuggestionsV2(BaseModel):
    """Structured output V2: metric definitions + dedupe judgments in one call."""

    metrics: list[MetricDefinition] = Field(default_factory=list)
    duplicates: list[DuplicateMetricNotice] = Field(default_factory=list)
    conflicts: list[MetricConflictInfo] = Field(default_factory=list)


class CustomMetricGenerateResponse(BaseModel):
    """Response chứa danh sách các gợi ý metric từ prompt tùy biến."""

    suggestions: list[MetricSuggestionItem] = Field(default_factory=list)
    duplicates: list[DuplicateMetricNotice] = Field(default_factory=list)
    dedupe_performed: bool = True


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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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
# Visual Dashboard (Singleton Layout Metadata)
# ---------------------------------------------------------------------------


DashboardChartType = Literal["kpi", "line", "area", "bar", "pie", "table"]
DashboardWidgetWidth = Literal["third", "half", "full"]
DashboardWidgetHeight = Literal["compact", "normal", "expanded"]


class DashboardWidgetConfig(BaseModel):
    """One persisted dashboard widget referencing approved semantic metadata."""

    id: str = Field(..., min_length=1, max_length=64, description="Stable client widget key")
    metric_id: int = Field(..., gt=0, description="Exactly one approved metric per widget")
    dimension_col_id: int | None = Field(default=None, gt=0)
    date_filter_column_id: int | None = Field(default=None, gt=0)
    time_grain: TimeGrain | None = None
    chart_type: DashboardChartType
    width: DashboardWidgetWidth
    height: DashboardWidgetHeight
    col_span: int | None = Field(default=None, ge=1, le=24, description="Custom 24-column grid span")
    row_span: int | None = Field(default=None, ge=1, le=48, description="Custom granular row blocks span")
    custom_title: str | None = Field(default=None, max_length=200)

    @field_validator("custom_title")
    @classmethod
    def normalize_custom_title(cls, value: str | None) -> str | None:
        """Collapse whitespace-only titles to null."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_chart_compatibility(self) -> DashboardWidgetConfig:
        """Enforce per-chart reference requirements from the canonical contract."""
        if self.chart_type == "kpi":
            if self.date_filter_column_id is None:
                raise ValueError("KPI widgets require date_filter_column_id")
            if self.dimension_col_id is not None or self.time_grain is not None:
                raise ValueError("KPI widgets must not define a dimension column or time grain")
        elif self.chart_type in ("line", "area"):
            if self.dimension_col_id is None or self.time_grain is None:
                raise ValueError("Line and area charts require a time dimension and grain")
        elif self.dimension_col_id is None:
            raise ValueError("Bar, pie, and table charts require a categorical dimension")
        return self


class DashboardLayout(BaseModel):
    """Ordered widget list persisted as the singleton dashboard layout."""

    widgets: list[DashboardWidgetConfig] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def reject_duplicate_widget_ids(self) -> DashboardLayout:
        """Keep widget identity stable and unique for drag-and-drop keys."""
        identifiers = [widget.id for widget in self.widgets]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Widget IDs must be unique within a layout")
        return self


class DashboardSaveRequest(BaseModel):
    """Request payload for saving the singleton dashboard layout."""

    layout: DashboardLayout
    expected_version: int = Field(
        ...,
        ge=0,
        description="API sentinel 0 creates the singleton; otherwise the exact stored version",
    )


class DashboardLayoutResponse(BaseModel):
    """Singleton dashboard state returned to clients."""

    db_id: int
    layout: DashboardLayout | None = None
    version: int = 0
    updated_at: datetime | None = None
    updated_by: int | None = None


# ---------------------------------------------------------------------------
# Canonical Relationships
# ---------------------------------------------------------------------------


class CanonicalRelationshipResponse(BaseModel):
    """Response for a canonical relationship between two semantic tables.

    Only relationships that are both technically valid and human-approved reach
    Flow 2 consumers; the governance fields are surfaced for transparency.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    connection_id: int
    from_entity_id: int
    to_entity_id: int
    relationship_type: str
    join_condition: str
    business_name: str = ""
    description: str | None = None
    validation_status: str = "valid"
    review_status: str = "pending_review"
    created_at: datetime


class SemanticCatalogColumn(BaseModel):
    """Expose a selectable canonical column to semantic query clients."""

    model_config = ConfigDict(from_attributes=True)

    column_id: int
    column_name: str
    business_name: str
    data_type: str
    is_time_dimension: bool = False
    is_primary_key: bool = False
    is_foreign_key: bool = False
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


class RecommendedDimensionItem(BaseModel):
    """Describe one recommended dimension item for a metric."""

    model_config = ConfigDict(from_attributes=True)

    column_id: int
    column_name: str
    business_name: str
    table_id: int
    table_name: str
    table_business_name: str
    tier: Literal["A", "B", "C", "D"]
    tier_label: str
    is_safe_join: bool
    requires_reaggregation: bool
    data_type: str
    cardinality_hint: int | None = None


class MetricDimensionsResponse(BaseModel):
    """List of recommended dimensions for a specific metric."""

    metric_id: int
    metric_name: str
    base_table: str
    dimensions: list[RecommendedDimensionItem] = Field(default_factory=list)


class FilterColumnItem(BaseModel):
    """Describe one safe, relevant filter column for a metric."""

    model_config = ConfigDict(from_attributes=True)

    column_id: int
    column_name: str
    business_name: str
    table_id: int
    table_name: str
    table_business_name: str
    group_type: Literal["base", "related"]
    data_type: str
    is_time_dimension: bool = False


class MetricFilterColumnsResponse(BaseModel):
    """Response containing valid, safe filter columns for a metric."""

    metric_id: int
    metric_name: str
    base_table: str
    columns: list[FilterColumnItem] = Field(default_factory=list)


class JoinPathOption(BaseModel):
    """One safe join-path candidate for a target entity from a base entity."""

    relationship_ids: list[int]
    entity_ids: list[int]
    labels: list[str]
    descriptions: list[str | None]


# ---------------------------------------------------------------------------
# Canonical Semantic Layer — Generate, Approve, Metrics List, History
# ---------------------------------------------------------------------------


class SemanticGenerateV2Response(BaseModel):
    """Response after re-running AI enrichment (POST /semantic/generate)."""

    db_id: int
    status: str = "draft"
    pending_tables: int = 0
    pending_columns: int = 0
    tables: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class SemanticApproveV2Response(BaseModel):
    """Response after approving all metrics in a semantic database."""

    db_id: int
    approved_count: int
    message: str = "Metrics approved successfully"


class MetricListItem(BaseModel):
    """A metric with version, status, and approval info."""

    model_config = ConfigDict(from_attributes=True)

    metric_id: int
    name: str
    definition: MetricDefinition | None = None
    source: str
    version: int
    status: str
    is_deleted: bool = False
    approved_by: int | None = None
    created_at: datetime
    has_pending_version: bool = False
    pending_version_number: int | None = None


class MetricVersionItem(BaseModel):
    """One version entry in a metric's history."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    definition: MetricDefinition | None = None
    status: str = "superseded"
    parent_version: int | None = None
    changed_by: int | None = None
    changed_by_name: str = ""
    change_reason: str = ""
    approved_by: int | None = None
    approved_by_name: str = ""
    approved_at: datetime | None = None
    created_at: datetime


class MetricHistoryResponse(BaseModel):
    """Response containing a metric's version history."""

    model_config = ConfigDict(from_attributes=True)

    metric_id: int
    metric_name: str
    live_version: int = 0
    versions: list[MetricVersionItem]


class SemanticTimeRange(BaseModel):
    """Normalized half-open date interval [start_date, end_date) in Asia/Ho_Chi_Minh."""

    column_id: int
    start_date: str
    end_date: str
    label: str


class ChatClarificationOption(BaseModel):
    """Self-contained pre-validated clarification option containing executable spec or action."""

    id: str
    label: str
    description: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    spec: SemanticQuerySpec | None = None
    action: str | None = None


class ChatClarificationSelection(BaseModel):
    """Validated resolution for exactly one clarification card (option, custom answer, or skip)."""

    assistant_message_id: str = Field(..., min_length=1, max_length=100)
    option_id: str | None = Field(default=None, min_length=1, max_length=100)
    custom_answer: str | None = Field(default=None, min_length=1, max_length=2000)
    skipped: bool = False

    @model_validator(mode="after")
    def _require_exactly_one_resolution_mode(self) -> ChatClarificationSelection:
        if self.custom_answer is not None:
            self.custom_answer = self.custom_answer.strip()
        active_modes = [self.option_id is not None, bool(self.custom_answer), self.skipped]
        if sum(active_modes) != 1:
            raise ValueError("Exactly one of option_id, custom_answer, or skipped must be provided")
        return self


class ChatClarificationPayload(BaseModel):
    """Structured clarification request returned to the user."""

    prompt: str
    options: list[ChatClarificationOption] = Field(default_factory=list)
    target_metric_name: str | None = None


class ClarificationResolution(BaseModel):
    """Canonical resolution written by the server for a clarification card."""

    status: Literal["answered", "skipped"]
    selected_option_id: str | None = None
    selected_label: str | None = None
    custom_answer: str | None = None


class ChatSemanticQueryResult(BaseModel):
    """Structured result of a semantic query execution for chat presentation."""

    spec: SemanticQuerySpec
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = Field(default=0)
    explanation: str
    sql: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticQueryInterpretation(BaseModel):
    """Semantic parse interpretation emitted by semantic_parse_node."""

    status: Literal["resolved", "needs_clarification"]
    spec: SemanticQuerySpec | None = None
    time_ranges: list[SemanticTimeRange] = Field(default_factory=list)
    clarification: ChatClarificationPayload | None = None
    rationale: str | None = None


# ---------------------------------------------------------------------------
# Chat Orchestrator (Multi-Agent)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request payload cho chatbot orchestrator endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Câu hỏi hoặc tin nhắn ngôn ngữ tự nhiên từ người dùng",
    )
    session_id: str | None = Field(default=None, min_length=36, max_length=36)
    client_message_id: str | None = Field(default=None, min_length=1, max_length=100)
    clarification_selection: ChatClarificationSelection | None = None


class ChatMessageResponse(BaseModel):
    """Persisted chat message returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    client_message_id: str | None = None
    sequence_no: int
    sender: Literal["user", "assistant", "system"]
    content: str
    intent: str | None = None
    metadata_json: dict[str, Any] | list[Any] | None = None
    created_at: datetime

    @computed_field
    @property
    def clarification(self) -> dict[str, Any] | None:
        """Surface stored clarification metadata so history reload can render resolved cards."""
        if isinstance(self.metadata_json, dict):
            return self.metadata_json.get("clarification")
        return None


class ChatSessionSummaryResponse(BaseModel):
    """Summary of one owned chat session."""

    id: str
    db_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatSessionDetailResponse(ChatSessionSummaryResponse):
    """Paginated chat session detail."""

    messages: list[ChatMessageResponse] = Field(default_factory=list)
    next_before_sequence: int | None = None


class ChatSessionUpdateRequest(BaseModel):
    """Request to rename a chat session."""

    title: str = Field(..., min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim whitespace before validating a session title."""
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Title cannot be empty")
        return normalized


class ChatResponse(BaseModel):
    """Response từ chatbot orchestrator sau khi phân loại intent."""

    intent: str = Field(
        ...,
        description="'chitchat', 'data_question', 'metric_query', 'semantic_query' hoặc 'out_of_scope'",
    )
    chat_response: str | None = Field(
        default=None,
        description="Câu trả lời ngôn ngữ tự nhiên cho chitchat/data_question/out_of_scope",
    )
    suggestions: list[Any] | None = Field(
        default=None,
        description="Danh sách Business Metrics JSON (khi intent = 'metric_query')",
    )
    duplicates: list[DuplicateMetricNotice] = Field(default_factory=list)
    dedupe_performed: bool = True
    suggestion_action: Literal["save_metric", "submit_metric_request"] | None = None
    diagnostics: dict[str, Any] | None = None
    semantic_query_result: ChatSemanticQueryResult | None = None
    clarification: ChatClarificationPayload | None = None
    clarification_resolution: ClarificationResolution | None = None
    session_id: str
    user_message_id: str | None = None
    assistant_message_id: str
    session: ChatSessionSummaryResponse | None = None


# ---------------------------------------------------------------------------
# Schema Sync & Self-Healing Schemas
# ---------------------------------------------------------------------------


class SchemaSyncLogResponse(BaseModel):
    """Audit log item representing a schema sync and self-healing operation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    semantic_db_id: int
    live_db_id: int | None = None
    trigger_type: str
    status: str
    old_fingerprint: str | None = None
    new_fingerprint: str | None = None
    changes_summary: dict[str, Any] | None = None
    details: str | None = None
    created_at: datetime


class SchemaSyncStatusResponse(BaseModel):
    """Current synchronization and drift status of a semantic database."""

    semantic_db_id: int
    in_sync: bool
    fingerprint: str | None = None
    last_synced_at: datetime | None = None
    sync_status: str = "synced"
    latest_log: SchemaSyncLogResponse | None = None
    drift_preview: dict[str, Any] | None = None


class SchemaSyncTriggerResponse(BaseModel):
    """Response returned when triggering an on-demand schema sync."""

    status: str
    log: SchemaSyncLogResponse
    message: str
