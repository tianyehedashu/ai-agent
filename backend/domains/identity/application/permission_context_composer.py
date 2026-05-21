"""PermissionContext 单一组装入口（JWT / Gateway / 后台任务 / 流式响应）。"""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.permission_context_factory import (
    build_permission_context_with_team_ids,
)
from domains.identity.domain.types import Principal
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    ensure_tenant_in_team_ids,
    get_permission_context,
    set_permission_context,
)

__all__ = ["PermissionContextComposer"]


class PermissionContextComposer:
    """组装并安装请求级 ``PermissionContext``。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compose_from_principal(self, principal: Principal) -> PermissionContext:
        user_id: uuid.UUID | None = None
        anonymous_id: str | None = None
        if principal.is_anonymous:
            anonymous_id = principal.get_anonymous_user_id()
        else:
            with suppress(ValueError, AttributeError):
                user_id = uuid.UUID(principal.id)
        return await build_permission_context_with_team_ids(
            self._db,
            user_id=user_id,
            anonymous_user_id=anonymous_id,
            role=principal.role,
        )

    async def compose_for_user_id(
        self,
        user_id: uuid.UUID,
        *,
        role: str = "user",
    ) -> PermissionContext:
        return await build_permission_context_with_team_ids(
            self._db,
            user_id=user_id,
            anonymous_user_id=None,
            role=role,
        )

    async def compose_for_owner(
        self,
        *,
        user_id: uuid.UUID | None,
        anonymous_user_id: str | None,
        role: str = "user",
    ) -> PermissionContext:
        return await build_permission_context_with_team_ids(
            self._db,
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            role=role,
        )

    async def compose_for_gateway_vkey(
        self,
        *,
        created_by_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        team_role: str,
    ) -> PermissionContext:
        ctx = await build_permission_context_with_team_ids(
            self._db,
            user_id=created_by_user_id,
            anonymous_user_id=None,
            role="user",
            team_id=tenant_id,
            team_role=team_role,
        )
        return ctx.with_team_ids(ensure_tenant_in_team_ids(ctx.team_ids, tenant_id))

    def install(self, ctx: PermissionContext) -> None:
        """安装上下文（HTTP 主路径在认证依赖中调用）。"""
        set_permission_context(ctx)

    @staticmethod
    @asynccontextmanager
    async def scoped(ctx: PermissionContext) -> AsyncIterator[PermissionContext]:
        """临时覆盖当前上下文，退出时恢复。"""
        previous = get_permission_context()
        set_permission_context(ctx)
        try:
            yield ctx
        finally:
            if previous is None:
                clear_permission_context()
            else:
                set_permission_context(previous)
