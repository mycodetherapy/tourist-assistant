"""Add guest sessions for try-without-register flow."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, None] = "d3a8b1c04e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "guest_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_id", sa.BigInteger(), sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True),
        sa.Column("full_runs_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partial_runs_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_guest_sessions_user_id"),
    )
    op.create_index("idx_guest_sessions_expires", "guest_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_guest_sessions_expires", table_name="guest_sessions")
    op.drop_table("guest_sessions")
    op.drop_column("users", "is_guest")
