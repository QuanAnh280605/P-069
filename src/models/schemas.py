from typing import Any, Literal

from pydantic import BaseModel, Field


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
    raw_schema: dict[str, Any] = Field(default_factory=dict)
    enriched_schema: dict[str, Any] = Field(default_factory=dict)
    suggested_metrics: list[dict[str, Any]] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    """BA/DA xác nhận duyệt và lưu chính thức Semantic Layer."""

    db_id: int = Field(..., description="ID DB cần lưu")


class ApproveResponse(BaseModel):
    """Response sau khi HITL approve và Save Node hoàn tất."""

    semantic_layer_id: int
    message: str = "Semantic Layer saved successfully"
