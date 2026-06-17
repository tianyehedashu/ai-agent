"""plan（上游/下游）配额单条删除写路径。

配额中心/模型详情删除 plan 配额（仅 ``plan_id``+``quota_id``、无 ``budget_id``）的入口。
鉴权口径与用量校正一致：能管这条配额才能删；删空套餐时连带删除空套餐，避免遗留
仅用于承载配额的自动套餐。
"""

from __future__ import annotations

from typing import Literal
import uuid

from domains.gateway.application.management.write_modules._base import (
    GatewayManagementWriteBaseMixin,
)
from libs.exceptions import NotFoundError, PermissionDeniedError, ValidationError


class QuotaPlanQuotaDeleteWritesMixin(GatewayManagementWriteBaseMixin):
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def delete_plan_quota(
        self,
        *,
        layer: Literal["upstream", "downstream"],
        plan_id: uuid.UUID,
        quota_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        is_team_admin: bool,
        member_self_service: bool = False,
    ) -> None:
        if layer == "upstream":
            await self._delete_upstream_plan_quota(
                plan_id=plan_id,
                quota_id=quota_id,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                is_platform_admin=is_platform_admin,
                is_team_admin=is_team_admin,
                member_self_service=member_self_service,
            )
        elif layer == "downstream":
            if member_self_service:
                raise PermissionDeniedError("成员自助仅可删除本人凭据的上游配额")
            if not is_team_admin and not is_platform_admin:
                raise PermissionDeniedError("需要团队管理员权限")
            await self._assert_entitlement_plan_in_team(
                plan_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
            deleted = await self._entitlement_plans.delete_quota(plan_id, quota_id)
            if not deleted:
                raise NotFoundError(f"下游配额不存在: {quota_id}")
            if not await self._entitlement_plans.list_quotas(plan_id):
                await self._entitlement_plans.delete(plan_id)
        else:
            raise ValidationError(f"不支持的配额层级: {layer}")

        await self._session.commit()
        await self._invalidate_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            upstream_changed=(layer == "upstream"),
        )

    async def _delete_upstream_plan_quota(
        self,
        *,
        plan_id: uuid.UUID,
        quota_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        is_team_admin: bool,
        member_self_service: bool,
    ) -> None:
        plan = await self._provider_plans.get(plan_id)
        if plan is None:
            raise NotFoundError(f"上游套餐不存在: {plan_id}")
        if not member_self_service and not is_team_admin and not is_platform_admin:
            raise PermissionDeniedError("需要团队管理员权限")
        # 凭据可写校验即删除授权（成员自助强制 is_platform_admin=False，只放行本人凭据）。
        await self._assert_upstream_credential_writable(
            plan.credential_id,
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin and not member_self_service,
            request_tenant_id=tenant_id,
        )
        deleted = await self._provider_plans.delete_quota(plan_id, quota_id)
        if not deleted:
            raise NotFoundError(f"上游配额不存在: {quota_id}")
        if not await self._provider_plans.list_quotas(plan_id):
            await self._provider_plans.delete(plan_id)


__all__ = ["QuotaPlanQuotaDeleteWritesMixin"]
