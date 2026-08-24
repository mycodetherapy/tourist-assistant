"""Add city_requests table for out-of-catalog city wishlist."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e2b3c4d5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "city_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("city_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            server_default="new",
            nullable=False,
        ),
        sa.Column("request_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_city_requests_normalized",
        "city_requests",
        ["normalized_name"],
        unique=False,
    )
    op.create_index(
        "idx_city_requests_status",
        "city_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_city_requests_status", table_name="city_requests")
    op.drop_index("idx_city_requests_normalized", table_name="city_requests")
    op.drop_table("city_requests")
