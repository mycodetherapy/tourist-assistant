"""Add poi_facts global cache table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d5f0a32c41"
down_revision: Union[str, Sequence[str], None] = "a7c4e9f21b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "poi_facts",
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("poi_name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=True),
        sa.Column("used_llm", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_index("idx_poi_facts_status", "poi_facts", ["status"])


def downgrade() -> None:
    op.drop_index("idx_poi_facts_status", table_name="poi_facts")
    op.drop_table("poi_facts")
