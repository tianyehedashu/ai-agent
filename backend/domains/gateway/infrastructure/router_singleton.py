"""
LiteLLM Router Singleton + Factory

提供全局唯一的 LiteLLM Router 实例，所有 OpenAI 兼容入口与内部桥接共用。

特性：
- 从 GatewayModel + ProviderCredential 拼装 model_list
- 跨进程 cooldown：使用 redis_url 共享 cooldown / TPM / RPM 状态
- 6 种 routing 策略，3 类 fallback
- 热重载：set_model_list / add_deployment / delete_deployment
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.gateway.domain.coding_agent_ua import apply_coding_agent_ua_litellm_params
from domains.gateway.domain.litellm_credential_extra_keys import (
    credential_extra_keys_for_litellm,
    litellm_api_key_param_name,
)
from domains.gateway.domain.litellm_model_id import (
    build_litellm_model_id,
    resolve_litellm_custom_llm_provider,
)
from domains.gateway.domain.policies.deployment_weight import coerce_deployment_weight
from domains.gateway.domain.router_model_name import (
    deployment_scope_team_id,
    encode_router_model_name,
)
from domains.gateway.domain.types import RoutingStrategy, credential_api_scope
from domains.gateway.domain.upstream_call_shape_policy import (
    resolve_effective_upstream_call_shape,
)
from domains.gateway.domain.upstream_endpoint import resolve_upstream_endpoint
from domains.gateway.domain.upstream_profile import UpstreamCallShape, UpstreamProtocol
from libs.crypto import decrypt_value, derive_encryption_key
from utils.logging import get_logger

if TYPE_CHECKING:
    from litellm.router import Router  # type: ignore[import-not-found]
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import (
        SystemGatewayModel,
        SystemGatewayRoute,
    )

logger = get_logger(__name__)


_router_instance: Router | None = None
_router_lock = asyncio.Lock()
_pii_guardrail_instance: Any | None = None


def _get_encryption_key() -> str:
    return derive_encryption_key(settings.secret_key.get_secret_value())


_provider_plan_pre_call_logger: Any | None = None


def ensure_gateway_callbacks() -> None:
    """注册 Gateway LiteLLM callbacks，供 Router 与内部直连兜底共用。"""
    import litellm

    # 兜底层：跨协议转译时丢弃目标 provider 不支持的字段。
    # 已知 Anthropic-only 字段（``context_management`` 等）由 domain 策略
    # ``anthropic_only_request_fields`` 在 anthropic_messages 入口显式剥离并写
    # warning 日志；此处只兜底未来上游新增/客户端自创但未纳入策略清单的字段。
    litellm.drop_params = True

    from domains.gateway.application.provider_plan_guard import (
        build_provider_plan_pre_call_logger,
    )
    from domains.gateway.infrastructure.callbacks.custom_logger import (
        get_logger_singleton,
    )
    from domains.gateway.infrastructure.guardrails.pii_guardrail import (
        _build_pii_guardrail_instance,
    )

    global _pii_guardrail_instance, _provider_plan_pre_call_logger  # pylint: disable=global-statement
    callbacks = list(litellm.callbacks or [])

    gateway_logger = get_logger_singleton()
    if gateway_logger not in callbacks:
        callbacks.append(gateway_logger)

    if _provider_plan_pre_call_logger is None:
        _provider_plan_pre_call_logger = build_provider_plan_pre_call_logger()
    if _provider_plan_pre_call_logger not in callbacks:
        callbacks.append(_provider_plan_pre_call_logger)

    if settings.gateway_default_guardrail_enabled:
        if _pii_guardrail_instance is None:
            _pii_guardrail_instance = _build_pii_guardrail_instance(
                guardrail_name="gateway_pii",
                default_enabled=True,
            )
        if _pii_guardrail_instance not in callbacks:
            callbacks.append(_pii_guardrail_instance)

    litellm.callbacks = callbacks


_PRICING_INJECT_KEYS: tuple[str, ...] = (
    "input_cost_per_token",
    "output_cost_per_token",
    "cache_creation_input_token_cost",
    "cache_read_input_token_cost",
)


def _build_litellm_params(
    *,
    real_model: str,
    provider: str,
    credential: ProviderCredential,
    rpm_limit: int | None,
    tpm_limit: int | None,
    tags: dict[str, Any] | None,
    pricing: dict[str, float] | None = None,
    upstream_call_shape: str | None = None,
) -> dict[str, Any]:
    """构造单个 deployment 的 litellm_params。

    ``pricing`` 为 deployment-level 单价（来自 ``upstream_model_pricing`` 当前有效行）。
    LiteLLM 在 ``model_list[i].litellm_params`` 中读到 ``input_cost_per_token`` 等字段时，
    会按 deployment 维度结算成本，从而让 ``cost-based-routing`` 在「同 ``model_name``
    多 deployment」（含跨 provider）情形下真正按价格择优。全局 ``litellm.register_model``
    仍然作为兜底。

    ``upstream_call_shape`` 决定出站协议面：``anthropic_native`` 时
    ``model`` 强制走 ``anthropic/`` 前缀（让 LiteLLM 使用 Anthropic Messages 通道）
    并解析 profile 的 Anthropic-native 根 ``api_base``。
    OpenAI-compat 出站直接用 ``real_model`` 不加 ``provider/`` 前缀——LiteLLM
    的 ``anthropic_messages()`` 在 Anthropic→OpenAI 格式翻译时无法正确剥离前缀，
    导致上游收到含前缀的非法模型名；路由靠 ``api_base`` + ``api_key`` +
    ``custom_llm_provider`` 组合就已足够。
    """
    profile_id = getattr(credential, "profile_id", None)
    call_shape = resolve_effective_upstream_call_shape(
        model_upstream_call_shape=upstream_call_shape,
        credential_profile_id=profile_id,
        provider=provider,
    )
    if call_shape == UpstreamCallShape.ANTHROPIC_NATIVE:
        model_id = build_litellm_model_id("anthropic", real_model)
        protocol = UpstreamProtocol.ANTHROPIC_NATIVE
        params: dict[str, Any] = {"model": model_id}
    else:
        model_id = real_model
        protocol = UpstreamProtocol.OPENAI_COMPAT
        params = {"model": model_id}
    encryption_key = _get_encryption_key()
    try:
        decrypted_api_key = decrypt_value(credential.api_key_encrypted, encryption_key)
    except Exception:  # pragma: no cover
        logger.warning("Failed to decrypt credential %s; falling back to raw value", credential.id)
        decrypted_api_key = credential.api_key_encrypted
    # Anthropic-native 通道统一用 ``api_key``；OpenAI-compat 沿用 provider 专属重命名。
    api_key_param = (
        "api_key"
        if call_shape == UpstreamCallShape.ANTHROPIC_NATIVE
        else litellm_api_key_param_name(provider)
    )
    params[api_key_param] = decrypted_api_key
    endpoint = resolve_upstream_endpoint(
        provider=provider,
        profile_id=profile_id,
        api_base=credential.api_base,
        api_bases=credential.api_bases,
        protocol=protocol,
    )
    if endpoint:
        params["api_base"] = endpoint
    # OpenAI-compat 出站：custom_llm_provider 必须在 endpoint 解析之后确定，
    # 因为 ``provider=openai`` + 自定义 ``api_base``（非 OpenAI 官方端点）
    # 必须使用 ``custom_openai``——否则 ``anthropic_messages()`` 会走
    # Responses API（``/responses``），而自定义端点只支持 ``/chat/completions``。
    if call_shape != UpstreamCallShape.ANTHROPIC_NATIVE:
        params["custom_llm_provider"] = resolve_litellm_custom_llm_provider(
            provider, api_base=endpoint
        )
    extra = credential.extra or {}
    for key in credential_extra_keys_for_litellm(provider):
        value = extra.get(key)
        if value is None or value == "":
            continue
        params[key] = value
    if rpm_limit:
        params["rpm"] = rpm_limit
    if tpm_limit:
        params["tpm"] = tpm_limit
    if pricing:
        for key in _PRICING_INJECT_KEYS:
            val = pricing.get(key)
            if val is not None:
                params[key] = val
    return apply_coding_agent_ua_litellm_params(
        params,
        credential_profile_id=profile_id,
        provider=provider,
    )


# Router deployment 专用，不应透传给 ``anthropic_messages`` 直连调用。
_ROUTER_ONLY_LITELLM_PARAM_KEYS: frozenset[str] = frozenset(
    {"rpm", "tpm", "weight", *_PRICING_INJECT_KEYS}
)


def filter_litellm_params_for_direct_anthropic(dep: dict[str, Any]) -> dict[str, Any]:
    """从 deployment 参数中剔除 Router 调度字段，避免传入 Anthropic Messages API。"""
    return {k: v for k, v in dep.items() if k not in _ROUTER_ONLY_LITELLM_PARAM_KEYS}


PricingLookup = dict[tuple[str, str, str], dict[str, float]]


def _pricing_for_model(
    src: GatewayModel | SystemGatewayModel,
    pricing_lookup: PricingLookup | None,
) -> dict[str, float] | None:
    if not pricing_lookup:
        return None
    cap = str(src.capability or "chat")
    return pricing_lookup.get((src.provider, src.real_model, cap))


def _build_deployment(
    *,
    model_name: str,
    src: GatewayModel | SystemGatewayModel,
    cred: ProviderCredential,
    via_route: str | None = None,
    pricing_lookup: PricingLookup | None = None,
) -> dict[str, Any]:
    """构造单个 deployment dict（model_list 一行）。"""
    pricing = _pricing_for_model(src, pricing_lookup)
    deployment_weight = coerce_deployment_weight(getattr(src, "weight", 1))
    litellm_params = _build_litellm_params(
        real_model=src.real_model,
        provider=src.provider,
        credential=cred,
        rpm_limit=src.rpm_limit,
        tpm_limit=src.tpm_limit,
        tags=src.tags,
        pricing=pricing,
        upstream_call_shape=getattr(src, "upstream_call_shape", None),
    )
    # LiteLLM simple_shuffle reads deployment["litellm_params"]["weight"] for
    # weighted selection; model_info.weight is retained for attribution/logging.
    litellm_params["weight"] = deployment_weight
    return {
        "model_name": model_name,
        "litellm_params": litellm_params,
        "model_info": {
            "id": str(src.id),
            "team_id": (
                str(src_tenant_id)
                if (src_tenant_id := getattr(src, "tenant_id", None)) is not None
                else None
            ),
            "capability": src.capability,
            "weight": deployment_weight,
            "gateway_model_name": src.name,
            "gateway_real_model": src.real_model,
            "gateway_provider": src.provider,
            "gateway_credential_id": str(cred.id),
            "gateway_credential_name": cred.name,
            "gateway_credential_scope": credential_api_scope(
                scope=getattr(cred, "scope", None),
                tenant_id=getattr(cred, "tenant_id", None),
            ),
            "gateway_via_route": via_route,
        },
    }


def _models_to_deployments(
    models: list[GatewayModel | SystemGatewayModel],
    credentials: dict[Any, ProviderCredential],
    pricing_lookup: PricingLookup | None = None,
) -> list[dict[str, Any]]:
    """把 GatewayModel / SystemGatewayModel 列表转成 LiteLLM Router 的 model_list。

    ``model_name`` 使用 ``gw/t/{tenant_id}/`` 或 ``gw/s/`` 前缀，避免跨租户同名冲突。
    """
    deployments: list[dict[str, Any]] = []
    for m in models:
        cred = credentials.get(m.credential_id)
        if cred is None:
            logger.warning("GatewayModel %s missing credential %s, skip", m.name, m.credential_id)
            continue
        deployments.append(
            _build_deployment(
                model_name=encode_router_model_name(deployment_scope_team_id(m), m.name),
                src=m,
                cred=cred,
                pricing_lookup=pricing_lookup,
            )
        )
    return deployments


def _routes_to_virtual_deployments(
    routes: list[GatewayRoute | SystemGatewayRoute],
    models: list[GatewayModel | SystemGatewayModel],
    credentials: dict[Any, ProviderCredential],
    reserved_model_names: frozenset[str],
    pricing_lookup: PricingLookup | None = None,
) -> list[dict[str, Any]]:
    """把 ``GatewayRoute.virtual_model`` 注册为多 deployment，激活 Router 内置负载均衡。

    一个 route 引用的 ``primary_models`` 中每条 ``GatewayModel`` 都被复制为一行
    ``model_name=virtual_model`` 的 deployment，由 ``routing_strategy`` 在它们之间调度。
    ``reserved_model_names`` 是已被 ``_models_to_deployments`` 占用的 ``GatewayModel.name``
    集合；当 virtual_model 与之冲突时跳过路由，避免同名 deployment 语义模糊。
    """
    if not routes:
        return []
    by_team_name: dict[tuple[str | None, str], GatewayModel | SystemGatewayModel] = {}
    for m in models:
        scope_key = str(deployment_scope_team_id(m)) if deployment_scope_team_id(m) else None
        by_team_name[(scope_key, m.name)] = m

    def _resolve(scope_id: Any, name: str) -> GatewayModel | SystemGatewayModel | None:
        scope_key = str(scope_id) if scope_id else None
        return by_team_name.get((scope_key, name)) or by_team_name.get((None, name))

    deployments: list[dict[str, Any]] = []
    for r in routes:
        if r.virtual_model in reserved_model_names:
            # 同名 GatewayModel 优先；路由仅作为 fallback 关系图
            continue
        for primary_name in r.primary_models or ():
            src = _resolve(deployment_scope_team_id(r), primary_name)
            if src is None:
                logger.warning(
                    "GatewayRoute %s primary %s has no matching GatewayModel, skip",
                    r.virtual_model,
                    primary_name,
                )
                continue
            cred = credentials.get(src.credential_id)
            if cred is None:
                logger.warning(
                    "GatewayRoute %s primary %s missing credential %s, skip",
                    r.virtual_model,
                    primary_name,
                    src.credential_id,
                )
                continue
            deployments.append(
                _build_deployment(
                    model_name=encode_router_model_name(
                        deployment_scope_team_id(r), r.virtual_model
                    ),
                    src=src,
                    cred=cred,
                    via_route=r.virtual_model,
                    pricing_lookup=pricing_lookup,
                )
            )
    return deployments


def _encode_fallback_model_name(
    route: GatewayRoute | SystemGatewayRoute,
    gateway_model_name: str,
    by_team_name: dict[tuple[str | None, str], GatewayModel | SystemGatewayModel],
) -> str:
    team_key = str(route.tenant_id) if route.tenant_id else None
    src = by_team_name.get((team_key, gateway_model_name)) or by_team_name.get(
        (None, gateway_model_name)
    )
    if src is not None:
        return encode_router_model_name(src.tenant_id, src.name)
    return gateway_model_name


def _routes_to_fallbacks(
    routes: list[GatewayRoute | SystemGatewayRoute],
    models: list[GatewayModel | SystemGatewayModel],
) -> tuple[list[dict[str, list[str]]], list[dict[str, list[str]]], list[dict[str, list[str]]]]:
    """从 routes 解出三类 fallback 列表（键与目标均为 Router 编码后的 ``model_name``）。"""
    by_team_name: dict[tuple[str | None, str], GatewayModel | SystemGatewayModel] = {}
    for m in models:
        scope_key = str(deployment_scope_team_id(m)) if deployment_scope_team_id(m) else None
        by_team_name[(scope_key, m.name)] = m

    general: list[dict[str, list[str]]] = []
    cp: list[dict[str, list[str]]] = []
    cw: list[dict[str, list[str]]] = []
    for r in routes:
        route_key = encode_router_model_name(deployment_scope_team_id(r), r.virtual_model)
        if r.fallbacks_general:
            general.append(
                {
                    route_key: [
                        _encode_fallback_model_name(r, n, by_team_name) for n in r.fallbacks_general
                    ]
                }
            )
        if r.fallbacks_content_policy:
            cp.append(
                {
                    route_key: [
                        _encode_fallback_model_name(r, n, by_team_name)
                        for n in r.fallbacks_content_policy
                    ]
                }
            )
        if r.fallbacks_context_window:
            cw.append(
                {
                    route_key: [
                        _encode_fallback_model_name(r, n, by_team_name)
                        for n in r.fallbacks_context_window
                    ]
                }
            )
    return general, cp, cw


def _litellm_routing_strategy(strategy: str | None) -> str:
    """将项目策略字面量映射为 LiteLLM Router 原生支持的 ``routing_strategy``。"""
    if strategy == RoutingStrategy.WEIGHTED_PICK.value:
        return RoutingStrategy.SIMPLE_SHUFFLE.value
    return strategy or RoutingStrategy.SIMPLE_SHUFFLE.value


def _resolve_strategy(routes: list[GatewayRoute | SystemGatewayRoute]) -> str:
    """全局策略选取：取最高频；如果都没设置默认 simple-shuffle

    （LiteLLM Router 单例只能一个 routing_strategy；
    不同路由可通过 model_list weight 体现差异；weighted-pick 映射为
    simple-shuffle，由 LiteLLM deployment weight 执行加权随机）
    """
    counts: dict[str, int] = {}
    for r in routes:
        strategy = _litellm_routing_strategy(str(r.strategy or "").strip())
        counts[strategy] = counts.get(strategy, 0) + 1
    if not counts:
        return RoutingStrategy.SIMPLE_SHUFFLE.value
    return max(counts.items(), key=lambda kv: kv[1])[0]


async def _load_upstream_pricing_lookup(db: AsyncSession) -> PricingLookup:
    """预取 active 上游单价表，形成 ``(provider, upstream_model, capability) → 单价`` lookup。"""
    from domains.gateway.infrastructure.repositories.pricing_repository import (
        UpstreamPricingRepository,
    )

    try:
        rows = await UpstreamPricingRepository(db).list_active()
    except Exception:  # pragma: no cover - 启动期表未就绪等情况
        logger.warning("Failed to load upstream pricing for Router deployments", exc_info=True)
        return {}
    lookup: PricingLookup = {}
    for row in rows:
        key = (row.provider, row.upstream_model, str(row.capability or "chat"))
        entry: dict[str, float] = {}
        if row.input_cost_per_token is not None:
            entry["input_cost_per_token"] = float(row.input_cost_per_token)
        if row.output_cost_per_token is not None:
            entry["output_cost_per_token"] = float(row.output_cost_per_token)
        if row.cache_creation_input_token_cost is not None:
            entry["cache_creation_input_token_cost"] = float(row.cache_creation_input_token_cost)
        if row.cache_read_input_token_cost is not None:
            entry["cache_read_input_token_cost"] = float(row.cache_read_input_token_cost)
        if entry:
            lookup[key] = entry
    return lookup


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
    from domains.gateway.infrastructure.repositories.system_credential_repository import (
        SystemProviderCredentialRepository,
    )

    model_repo = GatewayModelRepository(db)
    route_repo = GatewayRouteRepository(db)
    models = [
        *await model_repo.list_all_active(),
        *await model_repo.list_system(only_enabled=True),
    ]
    credentials_repo = ProviderCredentialRepository(db)
    system_credentials_repo = SystemProviderCredentialRepository(db)
    cred_ids = {m.credential_id for m in models}
    credentials: dict[Any, ProviderCredential] = {}
    if cred_ids:
        cred_list = await credentials_repo.list_by_ids(list(cred_ids))
        sys_cred_list = await system_credentials_repo.list_by_ids(cred_ids)
        for cred in [*cred_list, *sys_cred_list]:
            if cred.is_active:
                credentials[cred.id] = cred  # type: ignore[assignment]

    routes = [
        *await route_repo.list_all_active(),
        *await route_repo.list_system(only_enabled=True),
    ]
    pricing_lookup = await _load_upstream_pricing_lookup(db)
    deployments = _models_to_deployments(models, credentials, pricing_lookup)
    reserved_names = frozenset(m.name for m in models if m.enabled)
    deployments.extend(
        _routes_to_virtual_deployments(routes, models, credentials, reserved_names, pricing_lookup)
    )
    fb_general, fb_cp, fb_cw = _routes_to_fallbacks(routes, models)

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


def router_deployment_model_names(router: Any) -> frozenset[str]:
    """返回 Router 当前 ``model_list`` 中的 ``model_name`` 集合。"""
    model_list = getattr(router, "model_list", None) or []
    return frozenset(
        str(dep.get("model_name", ""))
        for dep in model_list
        if isinstance(dep, dict) and dep.get("model_name")
    )


async def ensure_router_deployment(
    db: AsyncSession,
    encoded_model_name: str,
) -> Router:
    """若内存 Router 缺少目标 deployment，先尝试增量 ``add_deployment``，再全量热重载。"""
    router = await get_router(db)
    encoded = encoded_model_name.strip()
    if not encoded:
        return router
    live_names = router_deployment_model_names(router)
    if encoded in live_names:
        return router
    logger.warning(
        "Router missing deployment %s (live=%d); trying incremental add",
        encoded,
        len(live_names),
    )
    if await _try_incremental_router_deployment(db, encoded):
        live_after = router_deployment_model_names(router)
        if encoded in live_after:
            logger.info("Router incremental deployment added %s", encoded)
            return router
    logger.warning(
        "Router incremental add missed %s; hot-reloading full model_list from DB",
        encoded,
    )
    return await reload_router(db)


async def _try_incremental_router_deployment(db: AsyncSession, encoded: str) -> bool:
    deployments = await _build_deployments_for_encoded_model(db, encoded)
    if not deployments:
        return False
    router = get_router_sync()
    if router is None:
        return False
    add_fn = getattr(router, "add_deployment", None)
    if not callable(add_fn):
        return False
    try:
        for dep in deployments:
            result = add_fn(deployment=dep)
            if asyncio.iscoroutine(result):
                await result
    except Exception:
        logger.warning(
            "Incremental router add_deployment failed for %s",
            encoded,
            exc_info=True,
        )
        return False
    return True


async def _resolve_router_credential(
    db: AsyncSession,
    credential_id: Any,
) -> ProviderCredential | None:
    from domains.gateway.infrastructure.repositories.credential_repository import (
        ProviderCredentialRepository,
    )
    from domains.gateway.infrastructure.repositories.system_credential_repository import (
        SystemProviderCredentialRepository,
    )

    cred = await ProviderCredentialRepository(db).get(credential_id)
    if cred is not None and cred.is_active:
        return cred
    sys_cred = await SystemProviderCredentialRepository(db).get(credential_id)
    if sys_cred is not None and sys_cred.is_active:
        return sys_cred  # type: ignore[return-value]
    return None


async def _build_deployments_for_encoded_model(
    db: AsyncSession,
    encoded: str,
) -> list[dict[str, Any]]:
    from domains.gateway.domain.router_model_name import decode_router_model_name
    from domains.gateway.infrastructure.repositories.model_repository import (
        GatewayModelRepository,
        GatewayRouteRepository,
    )

    decoded = decode_router_model_name(encoded)
    if decoded is None:
        return []
    team_id, client_name = decoded
    model_repo = GatewayModelRepository(db)
    route_repo = GatewayRouteRepository(db)
    pricing_lookup = await _load_upstream_pricing_lookup(db)

    record = await model_repo.resolve_by_name(team_id, client_name)
    route = None
    if record is None and team_id is not None:
        route = await route_repo.resolve_by_virtual_model(team_id, client_name)
        if route is not None:
            deployments: list[dict[str, Any]] = []
            for primary in route.primary_models or ():
                src = await model_repo.resolve_by_name(team_id, primary)
                if src is None:
                    continue
                cred = await _resolve_router_credential(db, src.credential_id)
                if cred is None:
                    continue
                deployments.append(
                    _build_deployment(
                        model_name=encoded,
                        src=src,
                        cred=cred,
                        via_route=route.virtual_model,
                        pricing_lookup=pricing_lookup,
                    )
                )
            return deployments

    if record is None:
        return []

    cred = await _resolve_router_credential(db, record.credential_id)
    if cred is None:
        return []
    return [
        _build_deployment(
            model_name=encoded,
            src=record,
            cred=cred,
            pricing_lookup=pricing_lookup,
        )
    ]


def get_router_sync() -> Router | None:
    """同步获取已初始化的 Router；未初始化返回 None（用于回调中查询）"""
    return _router_instance


def reset_router() -> None:
    """测试用：重置单例"""
    global _router_instance  # pylint: disable=global-statement
    _router_instance = None


__all__ = [
    "PricingLookup",
    "ensure_gateway_callbacks",
    "ensure_router_deployment",
    "filter_litellm_params_for_direct_anthropic",
    "get_router",
    "get_router_sync",
    "reload_router",
    "reset_router",
    "router_deployment_model_names",
]
