"""Request/response models for the HITL schema-review gate (Flow 1).

AI-proposed business names land in the Metadata Store as ``pending_review``; a
BA/DA edits them inline and approves before they count as officially stored.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewColumnItem(BaseModel):
    """One column awaiting or having passed BA/DA review."""

    model_config = ConfigDict(from_attributes=True)

    column_name: str
    business_name: str = ""
    description: str = ""
    data_type: str = ""
    ai_business_name: str | None = None
    ai_description: str | None = None
    review_status: str = "pending_review"
    is_primary_key: bool = False
    is_time_dimension: bool = False
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None


class ReviewTableItem(BaseModel):
    """One table awaiting or having passed BA/DA review, with its columns."""

    model_config = ConfigDict(from_attributes=True)

    table_id: int = Field(..., validation_alias="id")
    table_name: str
    business_name: str = ""
    description: str = ""
    physical_schema: str | None = None
    ai_business_name: str | None = None
    ai_description: str | None = None
    review_status: str = "pending_review"
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    columns: list[ReviewColumnItem] = Field(default_factory=list)


class SchemaReviewResponse(BaseModel):
    """The full review queue for one semantic database."""

    db_id: int
    status: str = Field(..., description="'pending_review' khi còn hàng đợi, ngược lại 'approved'")
    pending_tables: int = 0
    pending_columns: int = 0
    tables: list[ReviewTableItem] = Field(default_factory=list)


class SchemaApproveRequest(BaseModel):
    """Approve the whole review queue, or only the named tables."""

    table_names: list[str] | None = Field(
        default=None,
        description="Chỉ duyệt các bảng này; bỏ trống để duyệt toàn bộ hàng đợi",
    )


class SchemaApproveResponse(BaseModel):
    """Outcome of an approval, including what is still pending."""

    db_id: int
    approved_tables: int = 0
    approved_columns: int = 0
    pending_tables: int = 0
    pending_columns: int = 0
    status: str = "approved"


class MetricVersionDecisionRequest(BaseModel):
    """Approve or reject one pending metric version."""

    reason: str = Field(default="", max_length=1000, description="Lý do quyết định (audit log)")
