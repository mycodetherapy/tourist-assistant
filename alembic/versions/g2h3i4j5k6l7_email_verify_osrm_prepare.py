"""Add email verification and osrm_prepare_jobs."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verify_token_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verify_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "osrm_prepare_quota_used",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_table(
        "osrm_prepare_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "stage",
            sa.Text(),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "progress",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "counts_against_quota",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
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
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_osrm_prepare_jobs_status",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_osrm_prepare_jobs_progress",
        ),
    )
    op.create_index(
        "ix_osrm_prepare_jobs_user_created",
        "osrm_prepare_jobs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_osrm_prepare_jobs_slug_status",
        "osrm_prepare_jobs",
        ["slug", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_osrm_prepare_jobs_slug_status", table_name="osrm_prepare_jobs")
    op.drop_index("ix_osrm_prepare_jobs_user_created", table_name="osrm_prepare_jobs")
    op.drop_table("osrm_prepare_jobs")
    op.drop_column("users", "osrm_prepare_quota_used")
    op.drop_column("users", "email_verify_sent_at")
    op.drop_column("users", "email_verify_token_hash")
    op.drop_column("users", "email_verified_at")
