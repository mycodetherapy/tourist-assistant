"""Add users.last_seen_at for admin activity tracking."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e1f8a92d10"
down_revision: Union[str, Sequence[str], None] = "b8d5f0a32c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
