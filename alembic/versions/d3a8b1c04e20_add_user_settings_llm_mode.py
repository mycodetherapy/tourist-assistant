"""add user_settings.llm_mode

Revision ID: d3a8b1c04e20
Revises: c4e1f8a92d10
Create Date: 2026-08-04 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3a8b1c04e20"
down_revision: Union[str, None] = "c4e1f8a92d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "llm_mode",
            sa.Text(),
            nullable=False,
            server_default="none",
        ),
    )
    op.create_check_constraint(
        "ck_user_settings_llm_mode",
        "user_settings",
        "llm_mode IN ('none', 'platform', 'byok')",
    )
    op.execute(
        """
        UPDATE user_settings
        SET llm_mode = 'byok'
        WHERE llm_api_key_enc IS NOT NULL AND llm_api_key_enc <> ''
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_settings_llm_mode", "user_settings", type_="check")
    op.drop_column("user_settings", "llm_mode")
