"""
GatewayCustomLogger - LiteLLM CustomLogger 实现

记录所有 Gateway 调用：
- 成功（含流式末帧）
- 失败
- 缓存命中
- Fallback 链路

每条记录写入：
- gateway_request_logs（按月分区；成功请求可按配置采样）
- Redis 实时计数（用于 dashboard 与 budget；不受采样影响）
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal
import time
from typing import Any
import uuid

from bootstrap.config import settings
from domains.gateway.infrastructure.gateway_log_sampling import (
    should_persist_request_log_row,
)
from libs.db.database import get_session_context
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)


# Redis key 模板
REDIS_PREFIX = "gateway:metrics"


def _redis_keys(
    team_id: str | None, vkey_id: str | None, user_id: str | None, credential_id: str | None
) -> list[str]:
    """构建实时计数的 redis key 列表（多维度）"""
    keys: list[str] = []
    if team_id:
        keys.append(f"{REDIS_PREFIX}:team:{team_id}")
    if vkey_id:
        keys.append(f"{REDIS_PREFIX}:vkey:{vkey_id}")
    if user_id:
        keys.append(f"{REDIS_PREFIX}:user:{user_id}")
    if credential_id:
        keys.append(f"{REDIS_PREFIX}:credential:{credential_id}")
    return keys


def _import_custom_logger() -> Any:
    from litellm.integrations.custom_logger import CustomLogger

    return CustomLogger


_logger_instance: Any | None = None


def get_logger_singleton() -> Any:
    """获取全局 GatewayCustomLogger 单例（懒加载）"""
    global _logger_instance  # pylint: disable=global-statement
    if _logger_instance is None:
        _logger_instance = _build_logger_instance()
    return _logger_instance


class GatewayCustomLogger:
    """工厂入口（与 GatewayPiiGuardrail 一致，避免 import-time 加载 litellm）"""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return _build_logger_instance(*args, **kwargs)


def _build_logger_instance() -> Any:
    base_cls = _import_custom_logger()

    class _Impl(base_cls):  # type: ignore[misc, valid-type]
        async def async_log_success_event(
            self,
            kwargs: dict[str, Any],
            response_obj: Any,
            start_time: Any,
            end_time: Any,
        ) -> None:
            await _persist_event(
                kwargs=kwargs,
                response_obj=response_obj,
                start_time=start_time,
                end_time=end_time,
                status="success",
                error_code=None,
                error_message=None,
            )

        async def async_log_failure_event(
            self,
            kwargs: dict[str, Any],
            response_obj: Any,
            start_time: Any,
            end_time: Any,
        ) -> None:
            error = kwargs.get("exception") or kwargs.get("error") or response_obj
            error_code = type(error).__name__ if error else "UnknownError"
            error_message = str(error) if error else None
            await _persist_event(
                kwargs=kwargs,
                response_obj=response_obj,
                start_time=start_time,
                end_time=end_time,
                status="failed",
                error_code=error_code,
                error_message=error_message,
            )

        async def async_post_call_streaming_hook(
            self,
            user_api_key_dict: Any,
            response: Any,
        ) -> None:
            """流式末帧：通过 success_event 兜底，这里仅记录 ttfb"""
            return None

        async def async_dataset_hook(self, *args: Any, **kwargs: Any) -> None:
            """LiteLLM CustomLogger 抽象钩子；Gateway 不落 dataset。"""
            return None

    return _Impl()


# =============================================================================
# Persist
# =============================================================================


def _safe_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    return None


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    with suppress(ValueError, TypeError):
        return uuid.UUID(str(value))
    return None


def _build_pricing_snapshot(
    kwargs: dict[str, Any],
    response_obj: Any,
    cost_usd: Decimal,
) -> dict[str, Any]:
    """对齐 LiteLLM StandardLoggingPayload 子集 + 网关扩展字段。"""
    from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter

    slo = kwargs.get("standard_logging_object")
    snapshot: dict[str, Any] = {"response_cost": float(cost_usd)}
    if isinstance(slo, dict):
        if slo.get("model_map_information") is not None:
            snapshot["model_map_information"] = slo.get("model_map_information")
        snapshot["custom_pricing"] = slo.get("custom_pricing")
    from datetime import UTC, datetime

    fx = build_static_fx_adapter()
    snapshot["fx_rate_used"] = str(fx.get_rate("USD", "CNY"))
    snapshot["fx_source"] = "static"
    snapshot["fx_as_of"] = datetime.now(UTC).strftime("%Y-%m-%d")
    snapshot["display_currency"] = fx.default_display_currency()
    metadata = _extract_gateway_metadata(kwargs)
    from domains.gateway.application.pricing.pricing_display_cost import (
        resolve_downstream_display_cost_usd,
    )

    display = resolve_downstream_display_cost_usd(
        response_obj,
        metadata=metadata,
        model=kwargs.get("model"),
    )
    if display > 0:
        snapshot["response_cost"] = float(display)
    return snapshot


def _calc_cost(kwargs: dict[str, Any], response_obj: Any) -> tuple[Decimal, str]:
    """计算单次调用的上游成本（USD）及来源标签。"""
    from domains.gateway.application.pricing.upstream_cost_resolver import (
        resolve_upstream_cost_usd,
    )

    metadata = _extract_gateway_metadata(kwargs)
    slo = kwargs.get("standard_logging_object")
    slo_dict = slo if isinstance(slo, dict) else None
    return resolve_upstream_cost_usd(
        response=response_obj,
        model=kwargs.get("model"),
        metadata=metadata,
        standard_logging=slo_dict,
    )


def _extract_usage(response_obj: Any) -> tuple[int, int, int]:
    """提取 (input, output, cached) tokens"""
    if response_obj is None:
        return 0, 0, 0
    usage = getattr(response_obj, "usage", None) or {}

    def _usage_get(key: str, default: Any = None) -> Any:
        if isinstance(usage, dict):
            return usage.get(key, default)
        return getattr(usage, key, default)

    input_tokens = int(_usage_get("prompt_tokens", 0) or 0)
    output_tokens = int(_usage_get("completion_tokens", 0) or 0)
    cached_tokens = 0
    cache_details = _usage_get("prompt_tokens_details", None)
    if isinstance(cache_details, dict):
        cached_tokens = int(cache_details.get("cached_tokens", 0) or 0)
    elif cache_details is not None:
        cached_tokens = int(getattr(cache_details, "cached_tokens", 0) or 0)
    return input_tokens, output_tokens, cached_tokens


def _truncate_str(text: str, max_len: int) -> tuple[str, bool]:
    if max_len <= 0:
        return "", True
    if len(text) <= max_len:
        return text, False
    return text[:max_len], True


def _tool_calls_digest(tool_calls: Any, max_chars: int) -> str | None:
    """将 tool_calls 压成短文本，避免 JSON 爆量。"""
    if tool_calls is None:
        return None
    names: list[str] = []
    with suppress(Exception):
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function")
                if isinstance(fn, dict) and fn.get("name"):
                    names.append(str(fn["name"]))
                elif tc.get("name"):
                    names.append(str(tc["name"]))
    if not names:
        return None
    raw = f"n={len(names)}:" + ",".join(names)
    truncated, _ = _truncate_str(raw, max_chars)
    return truncated


def _serialize_messages_preview(messages: Any, max_chars: int) -> dict[str, Any] | None:
    """将 LiteLLM messages 压成单行摘要（截断）。"""
    if not isinstance(messages, list) or max_chars <= 0:
        return None
    parts: list[str] = []
    budget = max_chars
    truncated_any = False
    for m in messages:
        if not isinstance(m, dict) or budget <= 0:
            break
        role = str(m.get("role", ""))
        content = m.get("content", "")
        if not isinstance(content, str):
            content = str(content) if content is not None else ""
        line = f"{role}:{content}"
        piece, cut = _truncate_str(line, min(budget, max(64, budget // 2)))
        if cut:
            truncated_any = True
        parts.append(piece)
        budget -= len(piece) + 1
    if not parts:
        return None
    joined = "\n".join(parts)
    joined, cut2 = _truncate_str(joined, max_chars)
    return {"text": joined, "truncated": truncated_any or cut2}


def _summarize_response(
    response_obj: Any,
    *,
    max_response_chars: int,
    tool_calls_max_chars: int,
) -> dict[str, Any] | None:
    """提取响应摘要；``max_response_chars`` 控制 assistant 正文 preview 上限。"""
    if response_obj is None:
        return None
    summary: dict[str, Any] = {}
    with suppress(Exception):
        choices = getattr(response_obj, "choices", None) or []
        if choices:
            first = choices[0]
            msg = getattr(first, "message", None)
            if msg is not None:
                content = getattr(msg, "content", None) or ""
                if isinstance(content, str):
                    preview, cut = _truncate_str(content, max_response_chars)
                    summary["preview"] = preview
                    if cut:
                        summary["preview_truncated"] = True
                else:
                    summary["preview"] = None
                reasoning = getattr(msg, "reasoning_content", None)
                if isinstance(reasoning, str) and reasoning.strip():
                    r_prev, r_cut = _truncate_str(reasoning, max_response_chars)
                    summary["reasoning_preview"] = r_prev
                    if r_cut:
                        summary["reasoning_preview_truncated"] = True
                tc_digest = _tool_calls_digest(
                    getattr(msg, "tool_calls", None), tool_calls_max_chars
                )
                if tc_digest:
                    summary["tool_calls_digest"] = tc_digest
                summary["finish_reason"] = getattr(first, "finish_reason", None)
    return summary or None


def _extract_gateway_metadata(kwargs: dict[str, Any]) -> dict[str, Any]:
    """从 LiteLLM 回调 ``kwargs`` 中拿到 Gateway 自定义 metadata。

    LiteLLM Router / acompletion 在不同版本会把用户传入的 ``metadata`` 放到
    不同位置（顶层 ``metadata``、``litellm_params.metadata``、``standard_logging_object.metadata``
    等）。``_build_metadata`` 注入的字段都以 ``gateway_`` 开头，这里按已知路径合并，
    保证 ``gateway_team_id`` / ``gateway_user_id`` / ``gateway_vkey_id`` 不会因 LiteLLM
    内部搬运而丢失。
    """
    candidates: list[dict[str, Any]] = []
    for top_key in ("metadata", "litellm_metadata"):
        value = kwargs.get(top_key)
        if isinstance(value, dict):
            candidates.append(value)
    for container_key in ("litellm_params", "standard_logging_object", "optional_params"):
        container = kwargs.get(container_key)
        if isinstance(container, dict):
            inner = container.get("metadata")
            if isinstance(inner, dict):
                candidates.append(inner)

    merged: dict[str, Any] = {}
    for m in candidates:
        for k, v in m.items():
            if k not in merged or merged[k] is None:
                merged[k] = v
    return merged


_UPSTREAM_QUOTA_KEYWORDS: tuple[str, ...] = (
    "insufficient_quota",
    "quota_exceeded",
    "quota exceeded",
    "rate_limit_exceeded",
    "resource_exhausted",
    "resource has been exhausted",
    "you exceeded your current quota",
    "billing_hard_limit_reached",
    "exceeded_call_rate_limit",
)


def _is_upstream_quota_exhaustion(
    *, error_code: str | None, error_message: str | None, status_code: int | None
) -> bool:
    """识别上游"配额耗尽"类失败信号。

    覆盖 OpenAI/Anthropic/Google/Volcengine 等典型用语；保守宽松匹配，宁可
    多一次 force_exhaust（最坏后果是延迟 N 分钟恢复），不要漏掉一次（最坏后果
    是连续浪费上游调用）。
    """
    if status_code is not None and status_code in (402, 429):
        msg = (error_message or "").lower()
        for kw in _UPSTREAM_QUOTA_KEYWORDS:
            if kw in msg:
                return True
        # 单看 status 不足够：429 也可能是临时限流；要求 message 含关键字。
        # 但 402（支付/余额）几乎必然=配额耗尽。
        if status_code == 402:
            return True
    if error_code is None and error_message is None:
        return False
    blob = f"{error_code or ''} {error_message or ''}".lower()
    return any(kw in blob for kw in _UPSTREAM_QUOTA_KEYWORDS)


def _extract_status_code(exc: Any) -> int | None:
    """从 LiteLLM/HTTP 异常提取 status_code（兼容 dict 与对象）。"""
    if exc is None:
        return None
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    code = getattr(exc, "http_status", None)
    if isinstance(code, int):
        return code
    if isinstance(exc, dict):
        for k in ("status_code", "http_status", "status"):
            v = exc.get(k)
            if isinstance(v, int):
                return v
    return None


def _credential_from_model_info_kwargs(
    kwargs: dict[str, Any],
) -> tuple[uuid.UUID | None, str | None]:
    """从 LiteLLM Router deployment 的 model_info 取凭据（与 router_singleton 写入字段一致）。"""
    for container_key in ("litellm_params", "standard_logging_object"):
        container = kwargs.get(container_key)
        if not isinstance(container, dict):
            continue
        mi = container.get("model_info")
        if not isinstance(mi, dict):
            continue
        cid = _to_uuid(mi.get("gateway_credential_id"))
        raw_name = mi.get("gateway_credential_name")
        name: str | None = None
        if isinstance(raw_name, str) and raw_name.strip():
            name = raw_name.strip()[:100]
        if cid is not None or name is not None:
            return cid, name
    return None, None


def _deployment_from_model_info_kwargs(
    kwargs: dict[str, Any],
) -> tuple[uuid.UUID | None, str | None]:
    """从 LiteLLM Router deployment 的 ``model_info`` 取 ``GatewayModel`` 主键与注册别名。"""
    for container_key in ("litellm_params", "standard_logging_object"):
        container = kwargs.get(container_key)
        if not isinstance(container, dict):
            continue
        mi = container.get("model_info")
        if not isinstance(mi, dict):
            continue
        gid = _to_uuid(mi.get("id"))
        raw_alias = mi.get("gateway_model_name")
        alias: str | None = None
        if isinstance(raw_alias, str) and raw_alias.strip():
            alias = raw_alias.strip()[:200]
        if gid is not None:
            return gid, alias
    return None, None


def _gateway_provider_for_persist(kwargs: dict[str, Any], metadata: dict[str, Any]) -> Any | None:
    provider = metadata.get("gateway_provider")
    if provider is not None:
        return provider
    for container_key in ("litellm_params", "standard_logging_object"):
        container = kwargs.get(container_key)
        if not isinstance(container, dict):
            continue
        mi = container.get("model_info")
        if isinstance(mi, dict) and mi.get("gateway_provider"):
            return mi.get("gateway_provider")
    return None


def _credential_snapshots_for_persist(
    metadata: dict[str, Any], kwargs: dict[str, Any]
) -> tuple[uuid.UUID | None, str | None]:
    cred_id = _to_uuid(metadata.get("gateway_credential_id"))
    raw_snap = metadata.get("gateway_credential_name_snapshot")
    cred_name_snap: str | None = None
    if isinstance(raw_snap, str) and raw_snap.strip():
        cred_name_snap = raw_snap.strip()[:100]
    if cred_id is None:
        mid, mname = _credential_from_model_info_kwargs(kwargs)
        cred_id = mid
        if cred_name_snap is None and mname is not None:
            cred_name_snap = mname
    return cred_id, cred_name_snap


def _normalized_fallback_entries(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get("gateway_fallback_chain") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(x) for x in raw if x]


def _build_prompt_redacted(
    *,
    verbose_log: bool,
    kwargs_messages: Any,
    prompt_max: int,
    pii_redactions: Any,
) -> dict[str, Any] | None:
    messages_preview = (
        _serialize_messages_preview(kwargs_messages, prompt_max) if verbose_log else None
    )
    if not (pii_redactions or messages_preview):
        return None
    out: dict[str, Any] = {}
    if pii_redactions:
        out["redactions"] = pii_redactions
    if messages_preview:
        out["messages_preview"] = messages_preview
    return out


def _metadata_extra_non_gateway(metadata: dict[str, Any]) -> dict[str, Any] | None:
    extra = {
        k: v
        for k, v in metadata.items()
        if not k.startswith("gateway_") and k not in {"pii_prompt_hash", "pii_redactions"}
    }
    return extra or None


async def _persist_event(
    *,
    kwargs: dict[str, Any],
    response_obj: Any,
    start_time: Any,
    end_time: Any,
    status: str,
    error_code: str | None,
    error_message: str | None,
) -> None:
    """把单次调用持久化到 DB + Redis"""

    metadata = _extract_gateway_metadata(kwargs)

    team_id = _to_uuid(metadata.get("gateway_team_id"))
    user_id = _to_uuid(metadata.get("gateway_user_id"))
    vkey_id = _to_uuid(metadata.get("gateway_vkey_id"))

    # 一次性诊断：当 Gateway 归因字段全为空时，把 kwargs 顶层键打出来，
    # 便于定位 metadata 究竟丢在哪一层（LiteLLM 不同版本搬运路径不同）。
    if team_id is None and user_id is None and vkey_id is None:
        logger.warning(
            "Gateway request log without attribution; kwargs keys=%s, metadata keys=%s, model=%s",
            sorted(kwargs.keys()),
            sorted(metadata.keys()),
            kwargs.get("model"),
        )

    capability = str(metadata.get("gateway_capability", "chat"))
    route_name = metadata.get("gateway_route_name") or kwargs.get("model")
    real_model = getattr(response_obj, "model", None) or kwargs.get("model")
    provider = _gateway_provider_for_persist(kwargs, metadata)

    cred_id, cred_name_snap = _credential_snapshots_for_persist(metadata, kwargs)

    deploy_id, deploy_name = _deployment_from_model_info_kwargs(kwargs)

    entitlement_plan_id = _to_uuid(metadata.get("gateway_entitlement_plan_id"))
    provider_plan_id = _to_uuid(metadata.get("gateway_provider_plan_id"))

    input_tokens, output_tokens, cached_tokens = _extract_usage(response_obj)
    if status == "success":
        upstream_cost, cost_source = _calc_cost(kwargs, response_obj)
    else:
        upstream_cost, cost_source = Decimal("0"), "zero"
    from domains.gateway.application.pricing.pricing_settlement import (
        merge_pricing_snapshot,
        settle_request_log_amounts,
    )

    cost_usd, revenue_usd, settlement_extra = settle_request_log_amounts(
        metadata=metadata,
        litellm_cost_usd=upstream_cost,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
    )
    settlement_extra["cost_source"] = cost_source
    pricing_snapshot = merge_pricing_snapshot(
        _build_pricing_snapshot(kwargs, response_obj, cost_usd),
        settlement_extra,
        cost_usd=cost_usd,
        revenue_usd=revenue_usd,
    )

    start_dt = _safe_dt(start_time)
    end_dt = _safe_dt(end_time) or datetime.now(UTC)
    latency_ms = int((end_dt - start_dt).total_seconds() * 1000) if start_dt else 0
    ttfb_ms = metadata.get("gateway_ttfb_ms")
    if ttfb_ms is not None:
        with suppress(TypeError, ValueError):
            ttfb_ms = int(ttfb_ms)

    cache_hit = bool(metadata.get("gateway_cache_hit") or kwargs.get("cache_hit"))
    fallback_chain = _normalized_fallback_entries(metadata)

    request_id = metadata.get("gateway_request_id") or kwargs.get("litellm_call_id")
    prompt_hash = metadata.get("pii_prompt_hash")
    pii_redactions = metadata.get("pii_redactions") or []

    verbose_log = bool(metadata.get("gateway_store_full_messages"))
    prompt_max = int(
        metadata.get("gateway_log_prompt_max_chars")
        or settings.gateway_request_log_prompt_max_chars
    )
    response_max = int(
        metadata.get("gateway_log_response_max_chars")
        or (
            settings.gateway_request_log_response_verbose_max_chars
            if verbose_log
            else settings.gateway_request_log_response_preview_max_chars
        )
    )
    tool_cap = int(settings.gateway_request_log_tool_calls_summary_max_chars)

    prompt_redacted = _build_prompt_redacted(
        verbose_log=verbose_log,
        kwargs_messages=kwargs.get("messages"),
        prompt_max=prompt_max,
        pii_redactions=pii_redactions,
    )

    response_summary = _summarize_response(
        response_obj,
        max_response_chars=response_max,
        tool_calls_max_chars=tool_cap,
    )

    team_snapshot = metadata.get("gateway_team_snapshot")
    user_email_snapshot = metadata.get("gateway_user_email_snapshot")
    vkey_name_snapshot = metadata.get("gateway_vkey_name_snapshot")
    route_snapshot = metadata.get("gateway_route_snapshot")

    metadata_extra = _metadata_extra_non_gateway(metadata)

    litellm_call = kwargs.get("litellm_call_id")
    litellm_call_str = str(litellm_call) if litellm_call is not None else None
    request_id_str = str(request_id) if request_id else None
    persist_row = should_persist_request_log_row(
        status=status,
        cost_usd=float(cost_usd),
        request_id=request_id_str,
        litellm_call_id=litellm_call_str,
        success_sample_rate=settings.gateway_request_log_success_sample_rate,
        always_persist_non_success=settings.gateway_request_log_always_persist_non_success,
        always_persist_cost_above_usd=settings.gateway_request_log_always_persist_cost_above_usd,
        force_persist=verbose_log,
    )

    # ---------- 写 DB ----------
    if persist_row:
        try:
            from domains.gateway.infrastructure.repositories.request_log_repository import (
                RequestLogRepository,
            )

            async with get_session_context() as session:
                await RequestLogRepository(session).insert(
                    team_id=team_id,
                    user_id=user_id,
                    vkey_id=vkey_id,
                    team_snapshot=team_snapshot,
                    user_email_snapshot=user_email_snapshot,
                    vkey_name_snapshot=vkey_name_snapshot,
                    route_snapshot=route_snapshot,
                    credential_id=cred_id,
                    credential_name_snapshot=cred_name_snap,
                    entitlement_plan_id=entitlement_plan_id,
                    provider_plan_id=provider_plan_id,
                    deployment_gateway_model_id=deploy_id,
                    deployment_model_name=deploy_name,
                    capability=capability,
                    route_name=str(route_name) if route_name else None,
                    real_model=str(real_model) if real_model else None,
                    provider=str(provider) if provider else None,
                    status=status,
                    error_code=error_code,
                    error_message=error_message,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    cost_usd=cost_usd,
                    revenue_usd=revenue_usd,
                    pricing_snapshot=pricing_snapshot,
                    latency_ms=latency_ms,
                    ttfb_ms=ttfb_ms if isinstance(ttfb_ms, int) else None,
                    cache_hit=cache_hit,
                    fallback_chain=fallback_chain,
                    request_id=request_id_str,
                    prompt_hash=str(prompt_hash) if prompt_hash else None,
                    prompt_redacted=prompt_redacted,
                    response_summary=response_summary,
                    metadata_extra=metadata_extra,
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to persist gateway request log: %s", exc)

    # ---------- 流式 / 延迟成本：以 callback 落库金额为预算最终依据 ----------
    if status == "success" and cost_usd > 0:
        with suppress(Exception):
            from domains.gateway.application.budget_callback_settlement import (
                commit_budget_from_callback,
            )

            await commit_budget_from_callback(
                metadata=metadata,
                request_id=request_id_str,
                cost_usd=cost_usd,
                total_tokens=input_tokens + output_tokens,
                budget_model=str(route_name) if route_name else None,
            )

    # ---------- 写 Redis 实时计数 ----------
    with suppress(Exception):
        await _bump_redis_counters(
            team_id=str(team_id) if team_id else None,
            vkey_id=str(vkey_id) if vkey_id else None,
            user_id=str(user_id) if user_id else None,
            credential_id=str(cred_id) if cred_id else None,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

    # ---------- 上游配额耗尽信号 → 立即拉满本地 ProviderPlan ----------
    if status == "failed" and provider_plan_id is not None:
        with suppress(Exception):
            await _maybe_mark_provider_plan_upstream_exhausted(
                kwargs=kwargs,
                provider_plan_id=provider_plan_id,
                error_code=error_code,
                error_message=error_message,
            )


async def _maybe_mark_provider_plan_upstream_exhausted(
    *,
    kwargs: dict[str, Any],
    provider_plan_id: uuid.UUID,
    error_code: str | None,
    error_message: str | None,
) -> None:
    """检测上游"配额耗尽"信号并即时同步本地 ProviderPlan quota。

    本地 quota 永远是"礼貌的预测"，上游 429 才是真理；命中此分支 = 用真理收敛
    预测，避免后续连续浪费上游调用。
    """
    exc = kwargs.get("exception") or kwargs.get("error")
    status_code = _extract_status_code(exc)
    if not _is_upstream_quota_exhaustion(
        error_code=error_code,
        error_message=error_message,
        status_code=status_code,
    ):
        return
    from domains.gateway.application.provider_plan_guard import get_provider_plan_guard

    guard = get_provider_plan_guard()
    await guard.mark_upstream_exhausted(
        provider_plan_id,
        reason=f"upstream_signal:{error_code or status_code or 'unknown'}",
    )


async def _bump_redis_counters(
    *,
    team_id: str | None,
    vkey_id: str | None,
    user_id: str | None,
    credential_id: str | None,
    status: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
) -> None:
    client = await get_redis_client()
    keys = _redis_keys(team_id, vkey_id, user_id, credential_id)
    pipe = client.pipeline()
    bucket_minute = int(time.time() // 60)
    bucket_day = datetime.now(UTC).strftime("%Y%m%d")
    bucket_month = datetime.now(UTC).strftime("%Y%m")
    field = "ok" if status == "success" else "err"
    for key in keys:
        pipe.hincrby(f"{key}:m{bucket_minute}", "total", 1)
        pipe.hincrby(f"{key}:m{bucket_minute}", field, 1)
        pipe.expire(f"{key}:m{bucket_minute}", 3600)

        pipe.hincrby(f"{key}:d{bucket_day}", "total", 1)
        pipe.hincrby(f"{key}:d{bucket_day}", "tokens", input_tokens + output_tokens)
        pipe.hincrbyfloat(f"{key}:d{bucket_day}", "cost", float(cost_usd))
        pipe.expire(f"{key}:d{bucket_day}", 86400 * 35)

        pipe.hincrby(f"{key}:M{bucket_month}", "total", 1)
        pipe.hincrby(f"{key}:M{bucket_month}", "tokens", input_tokens + output_tokens)
        pipe.hincrbyfloat(f"{key}:M{bucket_month}", "cost", float(cost_usd))
        pipe.expire(f"{key}:M{bucket_month}", 86400 * 90)
    await pipe.execute()


__all__ = ["GatewayCustomLogger", "get_logger_singleton"]
