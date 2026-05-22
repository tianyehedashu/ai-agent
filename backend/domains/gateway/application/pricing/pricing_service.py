"""定价解析与 LiteLLM 注册表同步。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import logging
from typing import Any
import uuid

from domains.gateway.domain.money import MoneyUSD
from domains.gateway.domain.pricing_calculator import (
    CostBreakdown,
    PricingRate,
    TokenUsage,
    build_breakdown,
    calculate_cost_from_rate,
)
from domains.gateway.infrastructure.models.pricing_downstream import DownstreamModelPricing
from domains.gateway.infrastructure.models.pricing_upstream import UpstreamModelPricing
from domains.gateway.infrastructure.repositories.pricing_repository import (
    DownstreamPricingRepository,
    UpstreamPricingRepository,
)

logger = logging.getLogger(__name__)


# 进程内已注册键的版本指纹缓存。
# value = (version, input, output, cache_creation, cache_read, extra_repr)；
# 与 DB 当前活跃行不一致才再 register，避免启动/管理面/运行时重复写同一条。
_REGISTERED_FINGERPRINTS: dict[str, tuple[Any, ...]] = {}


def reset_litellm_pricing_register_cache() -> None:
    """测试用：清空已注册指纹缓存。"""
    _REGISTERED_FINGERPRINTS.clear()


class RateUnavailableError(Exception):
    """mirror 策略但上游无价。"""


@dataclass(frozen=True)
class ResolvedPricing:
    upstream: PricingRate | None
    downstream: PricingRate
    downstream_row: DownstreamModelPricing | None
    upstream_row: UpstreamModelPricing | None
    hit_chain: list[str]
    """与 ORM 行解耦的策略快照；缓存命中后 ``downstream_row`` 可能为 None。"""
    downstream_strategy: str | None = None


def resolved_inheritance_strategy(resolved: ResolvedPricing) -> str | None:
    """成员价/API 用策略；不访问可能已 detach 的 ORM 行。"""
    if resolved.downstream_strategy is not None:
        return resolved.downstream_strategy
    if resolved.downstream.inheritance_strategy is not None:
        return resolved.downstream.inheritance_strategy
    if "mirror" in resolved.hit_chain:
        return "mirror"
    if "manual" in resolved.hit_chain:
        return "manual"
    if "upstream_passthrough" in resolved.hit_chain:
        return "upstream_passthrough"
    return None


def _row_to_rate(row: UpstreamModelPricing | DownstreamModelPricing) -> PricingRate:
    strategy = getattr(row, "inheritance_strategy", None)
    return PricingRate(
        input_cost_per_token=row.input_cost_per_token or Decimal("0"),
        output_cost_per_token=row.output_cost_per_token or Decimal("0"),
        cache_creation_input_token_cost=row.cache_creation_input_token_cost,
        cache_read_input_token_cost=row.cache_read_input_token_cost,
        per_request_usd=getattr(row, "per_request_usd", None),
        version=row.version,
        source=getattr(row, "source", "manual"),
        inheritance_strategy=strategy,
    )


class PricingService:
    def __init__(
        self,
        upstream_repo: UpstreamPricingRepository,
        downstream_repo: DownstreamPricingRepository,
    ) -> None:
        self._upstream = upstream_repo
        self._downstream = downstream_repo

    async def resolve_upstream_rate(
        self,
        *,
        provider: str,
        upstream_model: str,
        capability: str,
        at: datetime | None = None,
    ) -> PricingRate | None:
        row = await self._upstream.get_active(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            at=at,
        )
        if row is None:
            return None
        return _row_to_rate(row)

    async def resolve_downstream_rate(
        self,
        *,
        tenant_id: uuid.UUID | None,
        entitlement_plan_id: uuid.UUID | None,
        gateway_model_id: uuid.UUID | None,
        provider: str,
        upstream_model: str,
        capability: str,
        at: datetime | None = None,
        use_cache: bool = True,
    ) -> ResolvedPricing:
        at = at or datetime.now(UTC)
        if use_cache:
            from domains.gateway.application.pricing.pricing_resolution_cache import (
                get_cached_resolution_async,
                pricing_resolution_cache_key,
            )

            key = pricing_resolution_cache_key(
                tenant_id=tenant_id,
                gateway_model_id=gateway_model_id,
                entitlement_plan_id=entitlement_plan_id,
                capability=capability,
            )
            cached = await get_cached_resolution_async(key)
            if cached is not None:
                return cached
        resolved = await self._resolve_downstream_rate_uncached(
            tenant_id=tenant_id,
            entitlement_plan_id=entitlement_plan_id,
            gateway_model_id=gateway_model_id,
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            at=at,
        )
        if use_cache:
            from domains.gateway.application.pricing.pricing_resolution_cache import (
                pricing_resolution_cache_key,
                set_cached_resolution_async,
            )

            await set_cached_resolution_async(
                pricing_resolution_cache_key(
                    tenant_id=tenant_id,
                    gateway_model_id=gateway_model_id,
                    entitlement_plan_id=entitlement_plan_id,
                    capability=capability,
                ),
                resolved,
            )
        return resolved

    async def _resolve_downstream_rate_uncached(
        self,
        *,
        tenant_id: uuid.UUID | None,
        entitlement_plan_id: uuid.UUID | None,
        gateway_model_id: uuid.UUID | None,
        provider: str,
        upstream_model: str,
        capability: str,
        at: datetime,
    ) -> ResolvedPricing:
        hit_chain: list[str] = []
        row: DownstreamModelPricing | None = None

        if entitlement_plan_id is not None:
            row = await self._downstream.get_active_for_scope(
                scope="entitlement_plan",
                scope_id=entitlement_plan_id,
                gateway_model_id=gateway_model_id,
                at=at,
            )
            if row is None and gateway_model_id is not None:
                row = await self._downstream.get_active_for_scope(
                    scope="entitlement_plan",
                    scope_id=entitlement_plan_id,
                    gateway_model_id=None,
                    at=at,
                )
            if row is not None:
                hit_chain.append("entitlement_plan")

        if row is None and tenant_id is not None:
            row = await self._downstream.get_active_for_scope(
                scope="tenant",
                scope_id=tenant_id,
                gateway_model_id=gateway_model_id,
                at=at,
            )
            if row is None and gateway_model_id is not None:
                row = await self._downstream.get_active_for_scope(
                    scope="tenant",
                    scope_id=tenant_id,
                    gateway_model_id=None,
                    at=at,
                )
            if row is not None:
                hit_chain.append("tenant")

        if row is None:
            row = await self._downstream.get_active_for_scope(
                scope="global",
                scope_id=None,
                gateway_model_id=gateway_model_id,
                at=at,
            )
            if row is None and gateway_model_id is not None:
                row = await self._downstream.get_active_for_scope(
                    scope="global",
                    scope_id=None,
                    gateway_model_id=None,
                    at=at,
                )
            if row is not None:
                hit_chain.append("global")

        upstream_row = await self._upstream.get_active(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            at=at,
        )
        upstream_rate = _row_to_rate(upstream_row) if upstream_row else None

        if row is None:
            if upstream_rate is None:
                raise RateUnavailableError(
                    f"No pricing for {provider}/{upstream_model}/{capability}"
                )
            hit_chain.append("upstream_passthrough")
            return ResolvedPricing(
                upstream=upstream_rate,
                downstream=upstream_rate,
                downstream_row=None,
                upstream_row=upstream_row,
                hit_chain=hit_chain,
                downstream_strategy="upstream_passthrough",
            )

        if row.inheritance_strategy == "mirror":
            if upstream_rate is None:
                raise RateUnavailableError("mirror downstream but upstream rate missing")
            hit_chain.append("mirror")
            return ResolvedPricing(
                upstream=upstream_rate,
                downstream=upstream_rate,
                downstream_row=row,
                upstream_row=upstream_row,
                hit_chain=hit_chain,
                downstream_strategy="mirror",
            )

        downstream_rate = _row_to_rate(row)
        hit_chain.append("manual")
        return ResolvedPricing(
            upstream=upstream_rate,
            downstream=downstream_rate,
            downstream_row=row,
            upstream_row=upstream_row,
            hit_chain=hit_chain,
            downstream_strategy=row.inheritance_strategy,
        )

    async def calculate(
        self,
        resolved: ResolvedPricing,
        usage: TokenUsage,
        *,
        provider_plan_hit: bool = False,
        entitlement_plan_hit: bool = False,
    ) -> CostBreakdown:
        upstream_zero = provider_plan_hit
        downstream_zero = entitlement_plan_hit
        if resolved.upstream is None:
            up_cost = MoneyUSD(amount=Decimal("0"))
        else:
            up_cost = calculate_cost_from_rate(resolved.upstream, usage, zero_amount=upstream_zero)
        down_cost = calculate_cost_from_rate(
            resolved.downstream,
            usage,
            zero_amount=downstream_zero,
        )
        snapshot: dict[str, object] = {
            "hit_chain": resolved.hit_chain,
            "downstream_strategy": resolved_inheritance_strategy(resolved),
            "upstream_version": resolved.upstream.version if resolved.upstream else None,
            "downstream_version": resolved.downstream.version,
        }
        return build_breakdown(
            upstream_cost=up_cost,
            downstream_revenue=down_cost,
            rate_snapshot=snapshot,
        )

    async def sync_to_litellm_registry(
        self,
        *,
        only_keys: Iterable[str] | None = None,
    ) -> int:
        """将 DB 活跃上游价目注册到 LiteLLM；返回**本次实际写入** LiteLLM 的模型数。

        设计原则：
        - 内置价目随 ``import litellm`` 已在 ``litellm.model_cost``，**不**重复注册全表副本；
        - 只 register「与上次指纹不同」的行，避免管理面写一次、启动一次都做全量写；
        - ``only_keys`` 用于「写一行后只刷一行」（管理面写入路径），不传则扫全表。
        """
        import litellm

        rows = await self._upstream.list_active()
        wanted: set[str] | None = None
        if only_keys is not None:
            wanted = {k for k in only_keys if k}
            if not wanted:
                return 0

        payload: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = row.upstream_model
            if not key:
                continue
            if wanted is not None and key not in wanted:
                continue
            entry = _build_litellm_pricing_entry(row)
            fingerprint = _pricing_fingerprint(row)
            if _REGISTERED_FINGERPRINTS.get(key) == fingerprint:
                continue
            payload[key] = entry
            _REGISTERED_FINGERPRINTS[key] = fingerprint
        if payload:
            litellm.register_model(payload)
            logger.info(
                "LiteLLM pricing registered: %d entries (keys=%s)",
                len(payload),
                sorted(payload.keys())[:5],
            )
        return len(payload)


def _build_litellm_pricing_entry(row: UpstreamModelPricing) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "input_cost_per_token": float(row.input_cost_per_token),
        "output_cost_per_token": float(row.output_cost_per_token),
    }
    if row.cache_creation_input_token_cost is not None:
        entry["cache_creation_input_token_cost"] = float(row.cache_creation_input_token_cost)
    if row.cache_read_input_token_cost is not None:
        entry["cache_read_input_token_cost"] = float(row.cache_read_input_token_cost)
    if row.extra:
        entry.update(row.extra)
    return entry


def _pricing_fingerprint(row: UpstreamModelPricing) -> tuple[Any, ...]:
    return (
        getattr(row, "version", None),
        str(row.input_cost_per_token),
        str(row.output_cost_per_token),
        str(row.cache_creation_input_token_cost) if row.cache_creation_input_token_cost else None,
        str(row.cache_read_input_token_cost) if row.cache_read_input_token_cost else None,
        repr(row.extra) if row.extra else None,
    )


def downstream_rate_to_custom_cost(
    rate: PricingRate,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, float]:
    """供 ``litellm.completion_cost(custom_cost_per_token=...)`` 与 metadata 注入使用。"""
    out: dict[str, float] = {
        "input_cost_per_token": float(rate.input_cost_per_token),
        "output_cost_per_token": float(rate.output_cost_per_token),
    }
    if rate.cache_creation_input_token_cost is not None:
        out["cache_creation_input_token_cost"] = float(rate.cache_creation_input_token_cost)
    if rate.cache_read_input_token_cost is not None:
        out["cache_read_input_token_cost"] = float(rate.cache_read_input_token_cost)
    if rate.per_request_usd is not None:
        out["per_request_usd"] = float(rate.per_request_usd)
    if extra:
        from domains.gateway.domain.policies.non_token_cost import NON_TOKEN_LITELLM_EXTRA_KEYS

        for key in NON_TOKEN_LITELLM_EXTRA_KEYS:
            raw = extra.get(key)
            if raw is not None:
                out[key] = float(raw)
    return out


__all__ = [
    "PricingService",
    "RateUnavailableError",
    "ResolvedPricing",
    "downstream_rate_to_custom_cost",
    "reset_litellm_pricing_register_cache",
    "resolved_inheritance_strategy",
]
