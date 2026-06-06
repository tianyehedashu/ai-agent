"""normalize openai real_model with provider prefix

Revision ID: 20260614_oaipfx
Revises: 20260614_gmcbu
Create Date: 2026-06-14

为 provider=openai 且 real_model 不含 '/' 的遗留记录统一添加 openai/ 前缀，
使 LiteLLM 能正确识别 OpenAI 兼容模型的 provider。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_oaipfx"
down_revision: str | None = "20260614_gmcbu"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UPDATE_SQL = """
    UPDATE {table}
    SET real_model = 'openai/' || real_model
    WHERE provider = 'openai'
      AND real_model NOT LIKE '%%/%%'
"""


def upgrade() -> None:
    op.execute(_UPDATE_SQL.format(table="gateway_models"))
    op.execute(_UPDATE_SQL.format(table="system_gateway_models"))


def downgrade() -> None:
    op.execute("""
        UPDATE gateway_models
        SET real_model = substring(real_model from 8)
        WHERE provider = 'openai'
          AND real_model LIKE 'openai/%%'
    """)
    op.execute("""
        UPDATE system_gateway_models
        SET real_model = substring(real_model from 8)
        WHERE provider = 'openai'
          AND real_model LIKE 'openai/%%'
    """)
