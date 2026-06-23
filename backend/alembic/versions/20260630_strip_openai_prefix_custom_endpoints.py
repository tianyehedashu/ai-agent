"""strip openai/ prefix from real_model on custom OpenAI-compat endpoints

Revision ID: 20260630_socp
Revises: 20260629_ptsl
Create Date: 2026-06-30

第三方 OpenAI 兼容端点（如 Agnes ``apihub.agnes-ai.com``）出站时 ``real_model`` 须为
裸上游 id（``agnes-1.5-flash``）。系统模型创建路径曾按 ``provider=openai`` 写入
``openai/agnes-1.5-flash``，导致上游 503 ``No available channel``。

仅修正 ``api_base`` 非 OpenAI 官方域名的凭据关联行；官方 OpenAI 不动。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260630_socp"
down_revision: str | None = "20260629_ptsl"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OPENAI_OFFICIAL = "https://api.openai.com"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE gateway_models AS gm
        SET real_model = substring(gm.real_model FROM 8)
        FROM provider_credentials AS pc
        WHERE gm.credential_id = pc.id
          AND gm.provider = 'openai'
          AND gm.real_model LIKE 'openai/%'
          AND pc.api_base IS NOT NULL
          AND pc.api_base NOT ILIKE '{_OPENAI_OFFICIAL}%'
        """
    )
    op.execute(
        f"""
        UPDATE system_gateway_models AS sgm
        SET real_model = substring(sgm.real_model FROM 8)
        FROM system_provider_credentials AS spc
        WHERE sgm.credential_id = spc.id
          AND sgm.provider = 'openai'
          AND sgm.real_model LIKE 'openai/%'
          AND spc.api_base IS NOT NULL
          AND spc.api_base NOT ILIKE '{_OPENAI_OFFICIAL}%'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE gateway_models AS gm
        SET real_model = 'openai/' || gm.real_model
        FROM provider_credentials AS pc
        WHERE gm.credential_id = pc.id
          AND gm.provider = 'openai'
          AND gm.real_model NOT LIKE '%/%'
          AND pc.api_base IS NOT NULL
          AND pc.api_base NOT ILIKE '{_OPENAI_OFFICIAL}%'
        """
    )
    op.execute(
        f"""
        UPDATE system_gateway_models AS sgm
        SET real_model = 'openai/' || sgm.real_model
        FROM system_provider_credentials AS spc
        WHERE sgm.credential_id = spc.id
          AND sgm.provider = 'openai'
          AND sgm.real_model NOT LIKE '%/%'
          AND spc.api_base IS NOT NULL
          AND spc.api_base NOT ILIKE '{_OPENAI_OFFICIAL}%'
        """
    )
