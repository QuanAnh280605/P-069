"""add client_message_id to chat_messages

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-08-18 20:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i4j5k6l7m8n9"
down_revision: str | Sequence[str] | None = "h3i4j5k6l7m8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    if bind is None:
        return False
    try:
        insp = sa.inspect(bind)
        return table_name in insp.get_table_names()
    except Exception:
        return False


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    if bind is None:
        return False
    try:
        insp = sa.inspect(bind)
        cols = [c["name"] for c in insp.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    if bind is None:
        return False
    try:
        insp = sa.inspect(bind)
        unique_constraints = [uc.get("name") for uc in insp.get_unique_constraints(table_name)]
        return constraint_name in unique_constraints
    except Exception:
        return False


def upgrade() -> None:
    """Ensure client_message_id column and unique constraint exist on chat_messages."""
    if _table_exists("chat_messages"):
        if not _column_exists("chat_messages", "client_message_id"):
            op.add_column(
                "chat_messages",
                sa.Column("client_message_id", sa.String(length=128), nullable=True),
            )
        if not _constraint_exists("chat_messages", "uq_chat_messages_session_client_id"):
            try:
                op.create_unique_constraint(
                    "uq_chat_messages_session_client_id",
                    "chat_messages",
                    ["session_id", "client_message_id"],
                )
            except Exception:
                pass


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("chat_messages"):
        if _constraint_exists("chat_messages", "uq_chat_messages_session_client_id"):
            op.drop_constraint("uq_chat_messages_session_client_id", "chat_messages", type_="unique")
        if _column_exists("chat_messages", "client_message_id"):
            op.drop_column("chat_messages", "client_message_id")
