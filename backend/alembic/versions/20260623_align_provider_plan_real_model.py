"""align provider_plans.real_model with gateway_models.real_model

Revision ID: 20260623_apprm
Revises: 20260622_gqpub_uat
Create Date: 2026-06-23

历史套餐曾写入裸 endpoint（ep-…）或缺 provider 前缀的 model id，而 Router
``gateway_real_model`` 与 ``GatewayModel.real_model`` 使用 canonical 形态
（如 ``volcengine/doubao-…``）。一次性对齐注册表，恢复 pre_call / 日志 / 配额展示。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260623_apprm"
down_revision: str | None = "20260622_gqpub_uat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REGISTERED_MODELS = """
    SELECT credential_id, real_model FROM gateway_models
    UNION ALL
    SELECT credential_id, real_model FROM system_gateway_models
"""


def upgrade() -> None:
    # 1) 裸 model id → ``{provider}/{id}``（与 ``build_litellm_model_id`` 一致）
    op.execute(
        f"""
        UPDATE provider_plans AS pp
        SET real_model = lower(pc.provider) || '/' || pp.real_model
        FROM provider_credentials AS pc
        WHERE pp.credential_id = pc.id
          AND pp.real_model IS NOT NULL
          AND strpos(pp.real_model, '/') = 0
          AND NOT EXISTS (
            SELECT 1 FROM ({_REGISTERED_MODELS}) AS reg
            WHERE reg.credential_id = pp.credential_id
              AND reg.real_model = pp.real_model
          )
          AND EXISTS (
            SELECT 1 FROM ({_REGISTERED_MODELS}) AS reg
            WHERE reg.credential_id = pp.credential_id
              AND reg.real_model = lower(pc.provider) || '/' || pp.real_model
          )
        """
    )

    # 2) 已带 provider 前缀但整串未注册：后缀与 canonical 一致则对齐
    op.execute(
        f"""
        UPDATE provider_plans AS pp
        SET real_model = reg.real_model
        FROM ({_REGISTERED_MODELS}) AS reg
        WHERE pp.credential_id = reg.credential_id
          AND pp.real_model IS NOT NULL
          AND pp.real_model <> reg.real_model
          AND lower(split_part(pp.real_model, '/', 2)) = lower(split_part(reg.real_model, '/', 2))
          AND NOT EXISTS (
            SELECT 1 FROM ({_REGISTERED_MODELS}) AS exact
            WHERE exact.credential_id = pp.credential_id
              AND exact.real_model = pp.real_model
          )
        """
    )

    # 3) 仍无法匹配且凭据仅注册一个模型：整凭据套餐键对齐唯一 canonical（历史 ep- 误填）
    op.execute(
        f"""
        UPDATE provider_plans AS pp
        SET real_model = sole.real_model
        FROM (
            SELECT reg.credential_id, min(reg.real_model) AS real_model
            FROM ({_REGISTERED_MODELS}) AS reg
            GROUP BY reg.credential_id
            HAVING count(*) = 1
        ) AS sole
        WHERE pp.credential_id = sole.credential_id
          AND pp.real_model IS NOT NULL
          AND pp.real_model <> sole.real_model
          AND NOT EXISTS (
            SELECT 1 FROM ({_REGISTERED_MODELS}) AS reg
            WHERE reg.credential_id = pp.credential_id
              AND reg.real_model = pp.real_model
          )
        """
    )


def downgrade() -> None:
    pass
