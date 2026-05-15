"""GatewayModelRepository / GatewayRouteRepository"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import case, func, or_, select

from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


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
        provider: str | None = None,
        credential_id: uuid.UUID | None = None,
    ) -> list[GatewayModel]:
        clauses = []
        if team_id is None:
            clauses.append(GatewayModel.team_id.is_(None))
            order_by = (GatewayModel.name,)
        else:
            clauses.append(or_(GatewayModel.team_id == team_id, GatewayModel.team_id.is_(None)))
            # 同名时团队行优先于全局行，避免 limit/去重语义不确定
            team_first = case((GatewayModel.team_id == team_id, 0), else_=1)
            order_by = (team_first, GatewayModel.name)
        if only_enabled:
            clauses.append(GatewayModel.enabled.is_(True))
        if capability:
            clauses.append(GatewayModel.capability == capability)
        if provider is not None:
            clauses.append(GatewayModel.provider == provider)
        if credential_id is not None:
            clauses.append(GatewayModel.credential_id == credential_id)
        stmt = select(GatewayModel).where(*clauses).order_by(*order_by)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_active(self) -> list[GatewayModel]:
        stmt = select(GatewayModel).where(GatewayModel.enabled.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, team_id: uuid.UUID | None, name: str) -> GatewayModel | None:
        clauses = [GatewayModel.name == name]
        if team_id is None:
            clauses.append(GatewayModel.team_id.is_(None))
            stmt = select(GatewayModel).where(*clauses).limit(1)
        else:
            clauses.append(or_(GatewayModel.team_id == team_id, GatewayModel.team_id.is_(None)))
            team_first = case((GatewayModel.team_id == team_id, 0), else_=1)
            stmt = (
                select(GatewayModel)
                .where(*clauses)
                .order_by(team_first, GatewayModel.name)
                .limit(1)
            )
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
            if not hasattr(model, key):
                continue
            # last_test_reason=None 表示成功测试后清空上次失败说明
            if key == "last_test_reason" or isinstance(value, bool) or value is not None:
                setattr(model, key, value)
        await self._session.flush()
        return model

    async def count_by_credential_id(self, credential_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(GatewayModel)
            .where(GatewayModel.credential_id == credential_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_models_grouped_by_credential(self) -> list[tuple[uuid.UUID, int]]:
        stmt = (
            select(GatewayModel.credential_id, func.count(GatewayModel.id))
            .group_by(GatewayModel.credential_id)
            .order_by(GatewayModel.credential_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(cid, int(cnt or 0)) for cid, cnt in rows]

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
            stmt = select(GatewayRoute).where(*clauses).limit(1)
        else:
            clauses.append(or_(GatewayRoute.team_id == team_id, GatewayRoute.team_id.is_(None)))
            team_first = case((GatewayRoute.team_id == team_id, 0), else_=1)
            stmt = (
                select(GatewayRoute)
                .where(*clauses)
                .order_by(team_first, GatewayRoute.virtual_model)
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
