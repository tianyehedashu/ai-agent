"""``DeploymentCooldownPort`` 的 LiteLLM Router 实现。

直接复用 Router 已有的 ``cooldown_cache``，使 quota 耗尽产生的 cooldown
与上游 429/401 等错误产生的 cooldown 在底层同源，跨进程 TTL 由 Router
的 Redis/DualCache 统一维护。
"""

from __future__ import annotations

import asyncio

from bootstrap.config import settings
from domains.gateway.domain.deployment_cooldown_port import DeploymentCooldownPort
from domains.gateway.infrastructure.router_singleton import get_router_sync
from utils.logging import get_logger

logger = get_logger(__name__)

# 429 作为 quota/rate-limit 类冷却的异常状态码，仅用于 Router cache 记录。
_QUOTA_COOLDOWN_STATUS_CODE = 429


class LiteLLMRouterDeploymentCooldownAdapter(DeploymentCooldownPort):
    """通过 LiteLLM Router cooldown_cache 实现 deployment 冷却。"""

    async def cooldown_deployment(
        self,
        *,
        deployment_id: str,
        reason: str,
    ) -> None:
        if not settings.gateway_quota_cooldown_enabled:
            return

        if not deployment_id or not isinstance(deployment_id, str):
            logger.debug("Skip quota cooldown: no deployment_id")
            return

        router = get_router_sync()
        if router is None:
            logger.warning("Skip quota cooldown: Router not initialized")
            return

        cooldown_cache = getattr(router, "cooldown_cache", None)
        if cooldown_cache is None:
            logger.warning("Skip quota cooldown: Router has no cooldown_cache")
            return

        effective_seconds = _resolve_cooldown_seconds()
        if effective_seconds <= 0:
            logger.debug("Skip quota cooldown: effective_seconds=%s", effective_seconds)
            return

        try:
            # ``add_deployment_to_cooldown`` 是 LiteLLM Router 的同步 API，内部会
            # 写内存缓存 + Redis。在线程池中执行，避免阻塞事件循环。
            await asyncio.to_thread(
                cooldown_cache.add_deployment_to_cooldown,
                model_id=deployment_id,
                original_exception=RuntimeError(f"quota-aware cooldown: {reason}"),
                exception_status=_QUOTA_COOLDOWN_STATUS_CODE,
                cooldown_time=effective_seconds,
            )
            logger.info(
                "Deployment %s put into quota cooldown for %.0fs (reason=%s)",
                deployment_id,
                effective_seconds,
                reason,
            )
        except Exception:  # pragma: no cover - cooldown 不应影响主路径
            logger.warning(
                "Failed to put deployment %s into quota cooldown",
                deployment_id,
                exc_info=True,
            )


def _resolve_cooldown_seconds() -> float:
    """把配置的 cooldown 时长收敛到允许范围内。

    时长完全由 Gateway 配置决定，与上游配额规则的窗口解耦；
    这样避免月度/年度配额规则产生数小时甚至数天的 cooldown。
    """
    seconds = float(settings.gateway_quota_cooldown_default_seconds)
    maximum = float(settings.gateway_quota_cooldown_max_seconds)

    # maximum == 0 表示业务选择不设置上限，此时仅保证非负。
    if maximum > 0:
        seconds = min(seconds, maximum)

    return max(0.0, seconds)


__all__ = ["LiteLLMRouterDeploymentCooldownAdapter"]
