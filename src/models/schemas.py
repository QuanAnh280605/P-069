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
    dialect: SchemaDialect
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

