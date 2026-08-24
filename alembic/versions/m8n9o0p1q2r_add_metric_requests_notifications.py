"""Add Member metric requests and persistent notifications."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m8n9o0p1q2r"
down_revision: str | Sequence[str] | None = "l7m8n9o0p1q2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create request and notification tables for the metric review workflow."""
    op.create_table(
        "metric_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("db_id", sa.Integer(), sa.ForeignKey("semantic_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "assistant_message_id", sa.String(36), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("suggestion_index", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_note", sa.Text()),
        sa.Column("metric_id", sa.Integer(), sa.ForeignKey("semantic_metrics.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_metric_requests_status"),
    )
    op.create_index("idx_metric_requests_db_status", "metric_requests", ["db_id", "status"])
    op.create_index("idx_metric_requests_requester", "metric_requests", ["requester_id", "created_at"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("metric_request_id", sa.Integer(), sa.ForeignKey("metric_requests.id", ondelete="CASCADE")),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_notifications_recipient_unread", "notifications", ["recipient_id", "read_at", "created_at"])


def downgrade() -> None:
    """Remove request and notification workflow tables."""
    op.drop_index("idx_notifications_recipient_unread", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("idx_metric_requests_requester", table_name="metric_requests")
    op.drop_index("idx_metric_requests_db_status", table_name="metric_requests")
    op.drop_table("metric_requests")
