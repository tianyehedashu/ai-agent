"""下游定价批量同步（mirror）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.pricing_repository import (
    DownstreamPricingRepository,
)


@dataclass(frozen=True)
class SyncReport:
    created: int
    skipped: int


class UpstreamSyncService:
    def __init__(
        self,
        downstream_repo: DownstreamPricingRepository,
        model_repo: GatewayModelRepository,
    ) -> None:
        self._downstream = downstream_repo
        self._models = model_repo

    async def bulk_mirror_from_upstream(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        team_id: uuid.UUID | None = None,
        model_ids: list[uuid.UUID] | None = None,
    ) -> SyncReport:
        created = 0
        skipped = 0
        if team_id is not None:
            models = await self._models.list_for_tenant(team_id, only_enabled=False)
        else:
            models = await self._models.list_system(only_enabled=False)
        if model_ids:
            id_set = set(model_ids)
            models = [m for m in models if m.id in id_set]
        existing = await self._downstream.list_for_scope(scope=scope, scope_id=scope_id)
        covered = {(r.gateway_model_id,) for r in existing if r.gateway_model_id is not None}
        for model in models:
            if (model.id,) in covered:
                skipped += 1
                continue
            await self._downstream.create(
                scope=scope,
                scope_id=scope_id,
                gateway_model_id=model.id,
                inheritance_strategy="mirror",
            )
            created += 1
        return SyncReport(created=created, skipped=skipped)

    async def convert_to_mirror(self, row_id: uuid.UUID) -> None:
        row = await self._downstream.get_by_id(row_id)
        if row is None:
            return
        await self._downstream.close_effective(row)
        await self._downstream.create(
            scope=row.scope,
            scope_id=row.scope_id,
            gateway_model_id=row.gateway_model_id,
            inheritance_strategy="mirror",
            effective_from=datetime.now(UTC),
        )

    async def convert_to_manual(
        self,
        row_id: uuid.UUID,
        *,
        input_cost_per_token,
        output_cost_per_token,
    ) -> None:
        from decimal import Decimal

        row = await self._downstream.get_by_id(row_id)
        if row is None:
            return
        await self._downstream.close_effective(row)
        await self._downstream.create(
            scope=row.scope,
            scope_id=row.scope_id,
            gateway_model_id=row.gateway_model_id,
            inheritance_strategy="manual",
            input_cost_per_token=Decimal(str(input_cost_per_token)),
            output_cost_per_token=Decimal(str(output_cost_per_token)),
            effective_from=datetime.now(UTC),
        )


__all__ = ["SyncReport", "UpstreamSyncService"]
