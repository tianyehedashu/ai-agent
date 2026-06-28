"""从 LiteLLM ``model_cost`` 同步上游价目（manual 特价不覆盖）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import logging
from typing import Any

from domains.gateway.domain.pricing.non_token_cost import merge_non_token_extra_from_litellm
from domains.gateway.infrastructure.repositories.pricing_repository import UpstreamPricingRepository

logger = logging.getLogger(__name__)

_PROTECTED_SOURCES = frozenset({"manual"})


@dataclass(frozen=True)
class LitellmUpstreamSyncReport:
    created: int
    updated: int
    skipped_manual: int

    def to_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped_manual": self.skipped_manual,
        }


def _parse_litellm_model_key(model_id: str) -> tuple[str, str]:
    if "/" in model_id:
        provider, _ = model_id.split("/", 1)
        return provider, model_id
    return "openai", model_id


_DEFAULT_CAPABILITY = "chat"


def _entry_to_rates(entry: dict[str, Any]) -> tuple[Decimal, Decimal] | None:
    inp = entry.get("input_cost_per_token")
    out = entry.get("output_cost_per_token")
    if inp is None or out is None:
        return None
    return Decimal(str(inp)), Decimal(str(out))


def _entry_to_sync_payload(
    entry: dict[str, Any],
) -> tuple[Decimal, Decimal, dict[str, Any] | None] | None:
    """Token 价、纯 extra 价或二者兼有均可同步。"""
    rates = _entry_to_rates(entry)
    extra = merge_non_token_extra_from_litellm(entry)
    extra_dict: dict[str, Any] | None = extra or None
    if rates is not None:
        inp_rate, out_rate = rates
        return inp_rate, out_rate, extra_dict
    if extra_dict:
        return Decimal("0"), Decimal("0"), extra_dict
    return None


class LitellmUpstreamPriceSyncService:
    def __init__(self, upstream_repo: UpstreamPricingRepository) -> None:
        self._upstream = upstream_repo

    async def _upsert_rate(
        self,
        *,
        provider: str,
        upstream_model: str,
        capability: str,
        inp_rate: Decimal,
        out_rate: Decimal,
        extra: dict[str, Any] | None,
        now: datetime,
    ) -> tuple[int, int, int]:
        existing = await self._upstream.get_active(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            at=now,
        )
        if existing is not None:
            if existing.source in _PROTECTED_SOURCES:
                return 0, 0, 1
            if (
                existing.input_cost_per_token == inp_rate
                and existing.output_cost_per_token == out_rate
                and existing.extra == extra
                and existing.source == "litellm_fallback"
            ):
                return 0, 0, 0
            await self._upstream.close_effective(existing)
            await self._upstream.create(
                provider=provider,
                upstream_model=upstream_model,
                capability=capability,
                input_cost_per_token=inp_rate,
                output_cost_per_token=out_rate,
                extra=extra,
                source="litellm_fallback",
                effective_from=now,
                version=existing.version + 1,
            )
            return 0, 1, 0
        await self._upstream.create(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            input_cost_per_token=inp_rate,
            output_cost_per_token=out_rate,
            extra=extra,
            source="litellm_fallback",
            effective_from=now,
        )
        return 1, 0, 0

    async def sync_from_litellm_model_cost(
        self,
        *,
        gateway_models: list[tuple[str, str, str]] | None = None,
        allowed_providers: set[str] | None = None,
    ) -> LitellmUpstreamSyncReport:
        """``gateway_models``: ``(provider, upstream_model, capability)`` 来自已注册模型。"""
        import litellm

        created = 0
        updated = 0
        skipped_manual = 0
        skipped_provider = 0
        now = datetime.now(UTC)
        model_cost: dict[str, dict[str, Any]] = dict(getattr(litellm, "model_cost", {}) or {})
        seen: set[tuple[str, str, str]] = set()

        for model_id, entry in model_cost.items():
            payload = _entry_to_sync_payload(entry)
            if payload is None:
                continue
            provider, upstream_model = _parse_litellm_model_key(model_id)
            if allowed_providers is not None and provider not in allowed_providers:
                skipped_provider += 1
                continue
            inp_rate, out_rate, extra = payload
            key = (provider, upstream_model, _DEFAULT_CAPABILITY)
            if key in seen:
                continue
            seen.add(key)
            c, u, s = await self._upsert_rate(
                provider=provider,
                upstream_model=upstream_model,
                capability=_DEFAULT_CAPABILITY,
                inp_rate=inp_rate,
                out_rate=out_rate,
                extra=extra,
                now=now,
            )
            created += c
            updated += u
            skipped_manual += s

        for provider, upstream_model, capability in gateway_models or []:
            if allowed_providers is not None and provider not in allowed_providers:
                skipped_provider += 1
                continue
            entry = model_cost.get(upstream_model)
            if entry is None:
                continue
            payload = _entry_to_sync_payload(entry)
            if payload is None:
                continue
            key = (provider, upstream_model, capability)
            if key in seen:
                continue
            seen.add(key)
            inp_rate, out_rate, extra = payload
            c, u, s = await self._upsert_rate(
                provider=provider,
                upstream_model=upstream_model,
                capability=capability,
                inp_rate=inp_rate,
                out_rate=out_rate,
                extra=extra,
                now=now,
            )
            created += c
            updated += u
            skipped_manual += s

        logger.info(
            "litellm upstream sync done created=%s updated=%s skipped_manual=%s skipped_provider=%s",
            created,
            updated,
            skipped_manual,
            skipped_provider,
        )
        return LitellmUpstreamSyncReport(
            created=created,
            updated=updated,
            skipped_manual=skipped_manual,
        )


__all__ = [
    "LitellmUpstreamPriceSyncService",
    "LitellmUpstreamSyncReport",
]
