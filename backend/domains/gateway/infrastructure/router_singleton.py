"""
LiteLLM Router Singleton + Factory

提供全局唯一的 LiteLLM Router 实例，所有 OpenAI 兼容入口与内部桥接共用。

特性：
- 从 GatewayModel + ProviderCredential 拼装 model_list
- 跨进程 cooldown：使用 redis_url 共享 cooldown / TPM / RPM 状态
- 5 种 routing 策略，3 类 fallback
- 热重载：set_model_list / add_deployment / delete_deployment
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from libs.crypto import decrypt_value, derive_encryption_key
from utils.logging import get_logger

if TYPE_CHECKING:
    from litellm.router import Router  # type: ignore[import-not-found]
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential

logger = get_logger(__name__)


_router_instance: Router | None = None
_router_lock = asyncio.Lock()
_pii_guardrail_instance: Any | None = None


def _get_encryption_key() -> str:
    return derive_encryption_key(settings.secret_key.get_secret_value())


def ensure_gateway_callbacks() -> None:
    """注册 Gateway LiteLLM callbacks，供 Router 与内部直连兜底共用。"""
    import litellm

    from domains.gateway.infrastructure.callbacks.custom_logger import (
        get_logger_singleton,
    )
    from domains.gateway.infrastructure.guardrails.pii_guardrail import (
        _build_pii_guardrail_instance,
    )

    global _pii_guardrail_instance  # pylint: disable=global-statement
    callbacks = list(litellm.callbacks or [])

    gateway_logger = get_logger_singleton()
    if gateway_logger not in callbacks:
        callbacks.append(gateway_logger)

    if settings.gateway_default_guardrail_enabled:
        if _pii_guardrail_instance is None:
            _pii_guardrail_instance = _build_pii_guardrail_instance(
                guardrail_name="gateway_pii",
                default_enabled=True,
            )
        if _pii_guardrail_instance not in callbacks:
            callbacks.append(_pii_guardrail_instance)

    litellm.callbacks = callbacks


def _build_litellm_params(
    *,
    real_model: str,
    provider: str,
    credential: ProviderCredential,
    rpm_limit: int | None,
    tpm_limit: int | None,
    tags: dict[str, Any] | None,
) -> dict[str, Any]:
    """构造单个 deployment 的 litellm_params"""
    params: dict[str, Any] = {
        "model": real_model,
    }
    encryption_key = _get_encryption_key()
    try:
        params["api_key"] = decrypt_value(credential.api_key_encrypted, encryption_key)
    except Exception:  # pragma: no cover
        logger.warning("Failed to decrypt credential %s; falling back to raw value", credential.id)
        params["api_key"] = credential.api_key_encrypted
    if credential.api_base:
        params["api_base"] = credential.api_base
    extra = credential.extra or {}
    for key in ("organization", "project_id", "region", "endpoint_id"):
        if key in extra:
            params[key] = extra[key]
    if rpm_limit:
        params["rpm"] = rpm_limit
    if tpm_limit:
        params["tpm"] = tpm_limit
    if tags:
        cost_in = tags.get("input_cost_per_token")
        cost_out = tags.get("output_cost_per_token")
        if cost_in is not None:
            params["input_cost_per_token"] = float(cost_in)
        if cost_out is not None:
            params["output_cost_per_token"] = float(cost_out)
    return params


def _models_to_deployments(
    models: list[GatewayModel],
    credentials: dict[Any, ProviderCredential],
) -> list[dict[str, Any]]:
    """把 GatewayModel 列表转成 LiteLLM Router 的 model_list"""
    deployments: list[dict[str, Any]] = []
    for m in models:
        cred = credentials.get(m.credential_id)
        if cred is None:
            logger.warning("GatewayModel %s missing credential %s, skip", m.name, m.credential_id)
            continue
        deployments.append(
            {
                "model_name": m.name,
                "litellm_params": _build_litellm_params(
                    real_model=m.real_model,
                    provider=m.provider,
                    credential=cred,
                    rpm_limit=m.rpm_limit,
                    tpm_limit=m.tpm_limit,
                    tags=m.tags,
                ),
                "model_info": {
                    "id": str(m.id),
                    "team_id": str(m.team_id) if m.team_id else None,
                    "capability": m.capability,
                    "weight": m.weight,
                    "gateway_model_name": m.name,
                    "gateway_credential_id": str(cred.id),
                    "gateway_credential_name": cred.name,
                    "gateway_credential_scope": cred.scope,
                },
            }
        )
    return deployments


def _routes_to_fallbacks(
    routes: list[GatewayRoute],
) -> tuple[list[dict[str, list[str]]], list[dict[str, list[str]]], list[dict[str, list[str]]]]:
    """从 routes 解出三类 fallback 列表"""
    general: list[dict[str, list[str]]] = []
    cp: list[dict[str, list[str]]] = []
    cw: list[dict[str, list[str]]] = []
    for r in routes:
        if r.fallbacks_general:
            general.append({r.virtual_model: list(r.fallbacks_general)})
        if r.fallbacks_content_policy:
            cp.append({r.virtual_model: list(r.fallbacks_content_policy)})
        if r.fallbacks_context_window:
            cw.append({r.virtual_model: list(r.fallbacks_context_window)})
    return general, cp, cw


def _resolve_strategy(routes: list[GatewayRoute]) -> str:
    """全局策略选取：取最高频；如果都没设置默认 simple-shuffle

    （LiteLLM Router 单例只能一个 routing_strategy；
    不同路由可通过 model_list weight 体现差异）
    """
    counts: dict[str, int] = {}
    for r in routes:
        counts[r.strategy] = counts.get(r.strategy, 0) + 1
    if not counts:
        return "simple-shuffle"
    return max(counts.items(), key=lambda kv: kv[1])[0]


async def _build_router_kwargs(
    db: AsyncSession,
) -> dict[str, Any]:
    """从数据库拼装 Router 构造参数"""
    from domains.gateway.infrastructure.repositories.credential_repository import (
        ProviderCredentialRepository,
    )
    from domains.gateway.infrastructure.repositories.model_repository import (
        GatewayModelRepository,
        GatewayRouteRepository,
    )

    models = await GatewayModelRepository(db).list_all_active()
    credentials_repo = ProviderCredentialRepository(db)
    cred_ids = {m.credential_id for m in models}
    credentials: dict[Any, ProviderCredential] = {}
    for cid in cred_ids:
        cred = await credentials_repo.get(cid)
        if cred is not None and cred.is_active:
            credentials[cid] = cred

    routes = await GatewayRouteRepository(db).list_all_active()
    deployments = _models_to_deployments(models, credentials)
    fb_general, fb_cp, fb_cw = _routes_to_fallbacks(routes)

    redis_url = settings.gateway_router_redis_url or settings.redis_url

    kwargs: dict[str, Any] = {
        "model_list": deployments,
        "routing_strategy": _resolve_strategy(routes),
        "num_retries": 2,
        "allowed_fails": settings.gateway_router_cooldown_threshold,
        "cooldown_time": settings.gateway_router_cooldown_seconds,
        "enable_pre_call_checks": True,
        "redis_url": redis_url,
        "set_verbose": False,
    }
    if fb_general:
        kwargs["fallbacks"] = fb_general
    if fb_cp:
        kwargs["content_policy_fallbacks"] = fb_cp
    if fb_cw:
        kwargs["context_window_fallbacks"] = fb_cw
    return kwargs


async def get_router(db: AsyncSession | None = None) -> Router:
    """获取全局 Router 单例（懒加载）

    Args:
        db: 仅初始化阶段使用；后续调用可不传
    """
    global _router_instance
    if _router_instance is not None:
        return _router_instance

    async with _router_lock:
        if _router_instance is not None:
            return _router_instance
        if db is None:
            raise RuntimeError(
                "Router not initialized. First call get_router(db) during app startup."
            )
        from litellm.router import Router

        # 注册全局回调（仅注册一次）
        ensure_gateway_callbacks()

        kwargs = await _build_router_kwargs(db)
        _router_instance = Router(**kwargs)
        logger.info(
            "LiteLLM Router initialized: %d deployments, strategy=%s",
            len(kwargs.get("model_list") or []),
            kwargs.get("routing_strategy"),
        )
    return _router_instance


async def reload_router(db: AsyncSession) -> Router:
    """热重载：重新拼装 model_list 并 set_model_list

    LiteLLM Router 提供 set_model_list 用于运行时无重启更新。
    fallback 列表通过属性赋值更新。
    """
    global _router_instance
    kwargs = await _build_router_kwargs(db)
    ensure_gateway_callbacks()
    if _router_instance is None:
        from litellm.router import Router

        _router_instance = Router(**kwargs)
        logger.info(
            "LiteLLM Router (cold-init) reloaded: %d deployments",
            len(kwargs.get("model_list") or []),
        )
        return _router_instance

    # 热更新部分参数
    set_model_list = getattr(_router_instance, "set_model_list", None)
    if callable(set_model_list):
        set_model_list(kwargs["model_list"])
    else:
        _router_instance.model_list = kwargs["model_list"]
    if "fallbacks" in kwargs:
        _router_instance.fallbacks = kwargs["fallbacks"]
    if "content_policy_fallbacks" in kwargs:
        _router_instance.content_policy_fallbacks = kwargs["content_policy_fallbacks"]
    if "context_window_fallbacks" in kwargs:
        _router_instance.context_window_fallbacks = kwargs["context_window_fallbacks"]
    _router_instance.routing_strategy = kwargs["routing_strategy"]
    logger.info("LiteLLM Router hot-reloaded: %d deployments", len(kwargs["model_list"]))
    return _router_instance


def get_router_sync() -> Router | None:
    """同步获取已初始化的 Router；未初始化返回 None（用于回调中查询）"""
    return _router_instance


def reset_router() -> None:
    """测试用：重置单例"""
    global _router_instance  # pylint: disable=global-statement
    _router_instance = None


__all__ = [
    "ensure_gateway_callbacks",
    "get_router",
    "get_router_sync",
    "reload_router",
    "reset_router",
]
