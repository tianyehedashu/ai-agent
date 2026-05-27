"""Backfill gateway_request_logs.provider from credential / deployment / real_model

Revision ID: 20260527_bfrlp
Revises: 20260527_api_bases
Create Date: 2026-05-27

Router CustomLogger 曾未写入 provider（metadata 被 LiteLLM 剥离且 model_info 缺字段），
导致调用统计按提供商维度出现「未知提供商」。本迁移仅回填历史行，新请求由代码修复。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_bfrlp"
down_revision: str | None = "20260527_api_bases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_STATEMENTS: tuple[str, ...] = (
    """
    UPDATE gateway_request_logs AS grl
    SET provider = pc.provider
    FROM provider_credentials AS pc
    WHERE grl.provider IS NULL
      AND grl.credential_id = pc.id
      AND pc.provider IS NOT NULL
    """,
    """
    UPDATE gateway_request_logs AS grl
    SET provider = spc.provider
    FROM system_provider_credentials AS spc
    WHERE grl.provider IS NULL
      AND grl.credential_id = spc.id
      AND spc.provider IS NOT NULL
    """,
    """
    UPDATE gateway_request_logs AS grl
    SET provider = gm.provider
    FROM gateway_models AS gm
    WHERE grl.provider IS NULL
      AND grl.deployment_gateway_model_id = gm.id
      AND gm.provider IS NOT NULL
    """,
    """
    UPDATE gateway_request_logs AS grl
    SET provider = sgm.provider
    FROM system_gateway_models AS sgm
    WHERE grl.provider IS NULL
      AND grl.deployment_gateway_model_id = sgm.id
      AND sgm.provider IS NOT NULL
    """,
    """
    UPDATE gateway_request_logs
    SET provider = CASE split_part(real_model, '/', 1)
        WHEN 'zai' THEN 'zhipuai'
        WHEN 'anthropic' THEN 'anthropic'
        WHEN 'dashscope' THEN 'dashscope'
        WHEN 'deepseek' THEN 'deepseek'
        WHEN 'volcengine' THEN 'volcengine'
        WHEN 'openai' THEN 'openai'
        ELSE provider
    END
    WHERE provider IS NULL
      AND real_model IS NOT NULL
      AND position('/' IN real_model) > 0
      AND split_part(real_model, '/', 1) IN (
          'zai', 'anthropic', 'dashscope', 'deepseek', 'volcengine', 'openai'
      )
    """,
)


def upgrade() -> None:
    conn = op.get_bind()
    for statement in _BACKFILL_STATEMENTS:
        conn.execute(sa.text(statement))


def downgrade() -> None:
    """数据回填不可逆。"""
