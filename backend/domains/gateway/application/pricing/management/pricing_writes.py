"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
)
from libs.exceptions import ValidationError
from utils.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal


logger = get_logger(__name__)


class PricingWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def upsert_upstream_pricing(
        self,
        *,
        provider: str,
        upstream_model: str,
        capability: str,
        currency: str,
        amount_per_million: dict[str, Any],
    ):
        from domains.gateway.application.pricing.management.pricing_management import (
            parse_amount_per_million,
        )
        from domains.gateway.application.pricing.pricing_service import PricingService
        from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter
        from domains.gateway.infrastructure.repositories.pricing_repository import (
            DownstreamPricingRepository,
            UpstreamPricingRepository,
        )

        fx = build_static_fx_adapter()
        inp, out, cc, cr, extra = parse_amount_per_million(amount_per_million, currency, fx)
        repo = UpstreamPricingRepository(self._session)
        now = datetime.now(UTC)
        existing = await repo.get_active(
            provider=provider, upstream_model=upstream_model, capability=capability, at=now
        )
        version = 1
        if existing is not None:
            await repo.close_effective(existing, at=now)
            version = existing.version + 1
        row = await repo.create(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            input_cost_per_token=inp,
            output_cost_per_token=out,
            cache_creation_input_token_cost=cc,
            cache_read_input_token_cost=cr,
            extra=extra,
            source="manual",
            effective_from=now,
            version=version,
        )
        svc = PricingService(repo, DownstreamPricingRepository(self._session))
        await svc.sync_to_litellm_registry(only_keys={upstream_model})
        from domains.gateway.application.pricing.pricing_resolution_cache import (
            invalidate_pricing_resolution_cache,
        )

        await invalidate_pricing_resolution_cache()
        return row

    async def sync_upstream_from_litellm(self, providers: Iterable[str] | None = None):
        from domains.gateway.application.pricing.pricing_resolution_cache import (
            invalidate_pricing_resolution_cache,
        )
        from domains.gateway.application.pricing.pricing_service import PricingService
        from domains.gateway.application.upstream.litellm_upstream_price_sync import (
            LitellmUpstreamPriceSyncService,
        )
        from domains.gateway.infrastructure.repositories.pricing_repository import (
            DownstreamPricingRepository,
            UpstreamPricingRepository,
        )

        upstream_repo = UpstreamPricingRepository(self._session)
        if providers is None:
            summaries = await self._creds.list_effective_provider_summaries()
            allowed_providers = {s.provider for s in summaries}
        else:
            allowed_providers = {p for p in providers if p}
        models = await GatewayModelRepository(self._session).list_system(only_enabled=False)
        gateway_models = [
            (m.provider, m.real_model, str(m.capability or "chat")) for m in models if m.real_model
        ]
        report = await LitellmUpstreamPriceSyncService(upstream_repo).sync_from_litellm_model_cost(
            gateway_models=gateway_models, allowed_providers=allowed_providers
        )
        pricing_svc = PricingService(upstream_repo, DownstreamPricingRepository(self._session))
        # 仅刷新本次涉及的模型键，避免再做全表 register_model。
        touched = {m for _, m, _ in gateway_models if m}
        if touched:
            await pricing_svc.sync_to_litellm_registry(only_keys=touched)
        await invalidate_pricing_resolution_cache()
        return report

    async def upsert_downstream_pricing(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        gateway_model_id: uuid.UUID | None,
        inheritance_strategy: str,
        currency: str = "CNY",
        amount_per_million: dict[str, Any] | None = None,
    ):
        from domains.gateway.domain.types import normalize_downstream_pricing_scope
        from domains.gateway.infrastructure.repositories.pricing_repository import (
            DownstreamPricingRepository,
        )

        scope = normalize_downstream_pricing_scope(scope)
        repo = DownstreamPricingRepository(self._session)
        now = datetime.now(UTC)
        existing = await repo.get_active_for_scope(
            scope=scope, scope_id=scope_id, gateway_model_id=gateway_model_id, at=now
        )
        version = 1
        if existing is not None:
            await repo.close_effective(existing, at=now)
            version = existing.version + 1
        if inheritance_strategy == "mirror":
            row = await repo.create(
                scope=scope,
                scope_id=scope_id,
                gateway_model_id=gateway_model_id,
                inheritance_strategy="mirror",
                effective_from=now,
                version=version,
            )
            from domains.gateway.application.pricing.pricing_resolution_cache import (
                invalidate_pricing_resolution_cache,
            )

            await invalidate_pricing_resolution_cache(
                tenant_id=scope_id if scope == "tenant" else None,
                gateway_model_id=gateway_model_id,
            )
            return row
        if amount_per_million is None:
            raise ValidationError("manual downstream pricing requires amount_per_million")
        from domains.gateway.application.pricing.management.pricing_management import (
            parse_amount_per_million,
        )
        from domains.gateway.infrastructure.fx.fx_static import build_static_fx_adapter

        fx = build_static_fx_adapter()
        inp, out, cc, cr, extra = parse_amount_per_million(amount_per_million, currency, fx)
        per_request_raw = amount_per_million.get("per_request")
        per_request_usd: Decimal | None = None
        if per_request_raw is not None:
            from decimal import Decimal

            per_request_usd = Decimal(str(per_request_raw))
            if currency.upper() == "CNY":
                per_request_usd = per_request_usd * fx.get_rate("CNY", "USD")
        row = await repo.create(
            scope=scope,
            scope_id=scope_id,
            gateway_model_id=gateway_model_id,
            inheritance_strategy="manual",
            input_cost_per_token=inp,
            output_cost_per_token=out,
            cache_creation_input_token_cost=cc,
            cache_read_input_token_cost=cr,
            per_request_usd=per_request_usd,
            extra=extra,
            effective_from=now,
            version=version,
        )
        from domains.gateway.application.pricing.pricing_resolution_cache import (
            invalidate_pricing_resolution_cache,
        )

        await invalidate_pricing_resolution_cache(
            tenant_id=scope_id if scope == "tenant" else None,
            gateway_model_id=gateway_model_id,
        )
        return row
