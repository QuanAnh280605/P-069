"""Shared HITL review-state columns for canonical schema metadata rows.

Applied to ``semantic_tables`` and ``semantic_columns`` so AI-proposed business
names stay in a ``pending_review`` state until a BA/DA approves them. The AI
proposal is preserved separately from the human-approved value so a reviewer can
always diff "what the model said" against "what we agreed on".
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, declarative_mixin, declared_attr, mapped_column

REVIEW_STATUS_PENDING = "pending_review"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUSES = (REVIEW_STATUS_PENDING, REVIEW_STATUS_APPROVED)
REVIEW_STATUS_CHECK = "review_status IN ('pending_review', 'approved')"


@declarative_mixin
class ReviewStateMixin:
    """Track AI proposal, last editor, and approval stamp for one metadata row."""

    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default=REVIEW_STATUS_PENDING)
    ai_business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr
    @classmethod
    def reviewed_by(cls) -> Mapped[int | None]:
        """Reference the user who approved this row into the Metadata Store."""
        return mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    @declared_attr
    @classmethod
    def updated_by(cls) -> Mapped[int | None]:
        """Reference the user who last edited this row inline."""
        return mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    @property
    def is_pending_review(self) -> bool:
        """Return True when this row still awaits BA/DA approval."""
        return self.review_status == REVIEW_STATUS_PENDING
