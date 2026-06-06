"""strip provider prefix from real_model

Revision ID: 20260614_oaipfx
Revises: 20260614_gmcbu
Create Date: 2026-06-14

剥离 real_model 中遗留的 LiteLLM provider 前缀（如 openai/、anthropic/、deepseek/ 等），
使 real_model 仅存储上游 API 接受的裸模型名（如 glm-5.1 而非 openai/glm-5.1）。
与 _build_litellm_params OpenAI-compat 出站路径一致：直接用 real_model 作为 model 参数。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_oaipfx"
down_revision: str | None = "20260614_gmcbu"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 需要剥离的 LiteLLM provider 前缀（与 litellm_model_id._PROVIDER_PREFIXES + zai 保持一致）
_STRIP_PREFIXES = (
    "openai/",
    "anthropic/",
    "dashscope/",
    "deepseek/",
    "volcengine/",
    "moonshot/",
    "zai/",
)

# 为每条前缀生成一条 UPDATE，用 LIKE 过滤 + substring 剥离
_UPGRADE_SQL_TEMPLATE = """
    UPDATE {table}
    SET real_model = substring(real_model from {prefix_len})
    WHERE real_model LIKE '{prefix}%%'
"""

_DOWNGRADE_SQL_TEMPLATE = """
    UPDATE {table}
    SET real_model = '{prefix}' || real_model
    WHERE provider = '{provider}'
      AND real_model NOT LIKE '%%/%%'
"""

# provider → prefix 映射（downgrade 用）
_PROVIDER_PREFIX_MAP = {
    "openai": "openai/",
    "anthropic": "anthropic/",
    "dashscope": "dashscope/",
    "deepseek": "deepseek/",
    "volcengine": "volcengine/",
    "moonshot": "moonshot/",
    "zhipuai": "zai/",
}


def upgrade() -> None:
    for table in ("gateway_models", "system_gateway_models"):
        for prefix in _STRIP_PREFIXES:
            op.execute(
                _UPGRADE_SQL_TEMPLATE.format(
                    table=table,
                    prefix=prefix,
                    prefix_len=len(prefix) + 1,
                )
            )


def downgrade() -> None:
    for table in ("gateway_models", "system_gateway_models"):
        for provider, prefix in _PROVIDER_PREFIX_MAP.items():
            op.execute(
                _DOWNGRADE_SQL_TEMPLATE.format(
                    table=table,
                    prefix=prefix,
                    provider=provider,
                )
            )
