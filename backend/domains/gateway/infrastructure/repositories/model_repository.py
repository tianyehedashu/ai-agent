"""GatewayModelRepository / GatewayRouteRepository"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute


class GatewayModelRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, model_id: uuid.UUID) -> GatewayModel | None:
        return await self._session.get(GatewayModel, model_id)

    async def list_for_team(
        self,
        team_id: uuid.UUID | None,
        *,
        only_enabled: bool = True,
        capability: str | None = None,
    ) -> list[GatewayModel]:
        clauses = []
        if team_id is None:
            clauses.append(GatewayModel.team_id.is_(None))
        else:
            clauses.append(or_(GatewayModel.team_id == team_id, GatewayModel.team_id.is_(None)))
        if only_enabled:
            clauses.append(GatewayModel.enabled.is_(True))
        if capability:
            clauses.append(GatewayModel.capability == capability)
        stmt = select(GatewayModel).where(*clauses).order_by(GatewayModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_active(self) -> list[GatewayModel]:
        stmt = select(GatewayModel).where(GatewayModel.enabled.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(
        self, team_id: uuid.UUID | None, name: str
    ) -> GatewayModel | None:
        clauses = [GatewayModel.name == name]
        if team_id is None:
            clauses.append(GatewayModel.team_id.is_(None))
        else:
            clauses.append(or_(GatewayModel.team_id == team_id, GatewayModel.team_id.is_(None)))
        stmt = select(GatewayModel).where(*clauses).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        team_id: uuid.UUID | None,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int = 1,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        tags: dict[str, Any] | None = None,
    ) -> GatewayModel:
        model = GatewayModel(
            team_id=team_id,
            name=name,
            capability=capability,
            real_model=real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=tags,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def update(
        self,
        model_id: uuid.UUID,
        **fields: Any,
    ) -> GatewayModel | None:
        model = await self.get(model_id)
        if model is None:
            return None
        for key, value in fields.items():
            if hasattr(model, key) and value is not None:
                setattr(model, key, value)
        await self._session.flush()
        return model

    async def delete(self, model_id: uuid.UUID) -> bool:
        model = await self.get(model_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True


class GatewayRouteRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, route_id: uuid.UUID) -> GatewayRoute | None:
        return await self._session.get(GatewayRoute, route_id)

    async def list_for_team(
        self,
        team_id: uuid.UUID | None,
        *,
        only_enabled: bool = True,
    ) -> list[GatewayRoute]:
        clauses = []
        if team_id is None:
            clauses.append(GatewayRoute.team_id.is_(None))
        else:
            clauses.append(or_(GatewayRoute.team_id == team_id, GatewayRoute.team_id.is_(None)))
        if only_enabled:
            clauses.append(GatewayRoute.enabled.is_(True))
        stmt = select(GatewayRoute).where(*clauses).order_by(GatewayRoute.virtual_model)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_active(self) -> list[GatewayRoute]:
        stmt = select(GatewayRoute).where(GatewayRoute.enabled.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_virtual_model(
        self, team_id: uuid.UUID | None, virtual_model: str
    ) -> GatewayRoute | None:
        clauses = [
            GatewayRoute.virtual_model == virtual_model,
            GatewayRoute.enabled.is_(True),
        ]
        if team_id is None:
            clauses.append(GatewayRoute.team_id.is_(None))
        else:
            clauses.append(or_(GatewayRoute.team_id == team_id, GatewayRoute.team_id.is_(None)))
        stmt = (
            select(GatewayRoute)
            .where(*clauses)
            .order_by(GatewayRoute.team_id.desc().nullslast())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        team_id: uuid.UUID | None,
        virtual_model: str,
        primary_models: list[str],
        fallbacks_general: list[str] | None = None,
        fallbacks_content_policy: list[str] | None = None,
        fallbacks_context_window: list[str] | None = None,
        strategy: str = "simple-shuffle",
        retry_policy: dict[str, Any] | None = None,
    ) -> GatewayRoute:
        route = GatewayRoute(
            team_id=team_id,
            virtual_model=virtual_model,
            primary_models=primary_models,
            fallbacks_general=fallbacks_general or [],
            fallbacks_content_policy=fallbacks_content_policy or [],
            fallbacks_context_window=fallbacks_context_window or [],
            strategy=strategy,
            retry_policy=retry_policy,
        )
        self._session.add(route)
        await self._session.flush()
        return route

    async def update(self, route_id: uuid.UUID, **fields: Any) -> GatewayRoute | None:
        route = await self.get(route_id)
        if route is None:
            return None
        for key, value in fields.items():
            if hasattr(route, key) and value is not None:
                setattr(route, key, value)
        await self._session.flush()
        return route

    async def delete(self, route_id: uuid.UUID) -> bool:
        route = await self.get(route_id)
        if route is None:
            return False
        await self._session.delete(route)
        await self._session.flush()
        return True


__all__ = ["GatewayModelRepository", "GatewayRouteRepository"]
