"""删除 real_model 未在凭据注册的孤儿 provider_plans

Revision ID: 20260618_pop
Revises: 20260617_vktg
Create Date: 2026-06-18

上游批量配额曾将同一 real_model 笛卡尔积写入全部凭据，产生无注册模型支撑的
ProviderPlan。本迁移删除此类孤儿行；``real_model IS NULL`` 的整凭据套餐保留。
"""

from collections.abc import Sequence

from alembic import op
from utils.logging import get_logger

logger = get_logger(__name__)

revision: str = "20260618_pop"
down_revision: str | None = "20260617_vktg"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ORPHAN_PLAN_IDS = """
SELECT p.id
FROM provider_plans p
WHERE p.real_model IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM gateway_models gm
      WHERE gm.credential_id = p.credential_id
        AND gm.real_model = p.real_model
  )
  AND NOT EXISTS (
      SELECT 1 FROM system_gateway_models sgm
      WHERE sgm.credential_id = p.credential_id
        AND sgm.real_model = p.real_model
  )
"""


def _bump_provider_plan_config_cache_version_best_effort() -> None:
    """迁移删 plan 后 bump Redis 版本号，避免热路径仍命中已删套餐缓存。"""
    try:
        import redis

        from bootstrap.config import settings

        kwargs: dict[str, object] = {"decode_responses": True}
        if settings.redis_username:
            kwargs["username"] = settings.redis_username
        if settings.redis_password:
            kwargs["password"] = settings.redis_password
        client = redis.from_url(settings.redis_url, **kwargs)
        client.incr("gw:provider_plan_cfg:ver")
        client.close()
    except Exception:
        logger.warning(
            "provider plan cache version bump skipped after orphan prune migration",
            exc_info=True,
        )


def upgrade() -> None:
    op.execute(
        f"""
        DELETE FROM provider_plan_quotas
        WHERE plan_id IN ({_ORPHAN_PLAN_IDS})
        """
    )
    op.execute(
        f"""
        DELETE FROM provider_plans
        WHERE id IN ({_ORPHAN_PLAN_IDS})
        """
    )
    _bump_provider_plan_config_cache_version_best_effort()


def downgrade() -> None:
    """数据删除不可恢复。"""
