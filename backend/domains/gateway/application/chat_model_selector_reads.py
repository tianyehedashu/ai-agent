"""聊天模型选择器读侧：readiness 与凭据计数（Gateway Application）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.billing_context import BillingContext, resolve_billing_context
from domains.gateway.domain.policies.chat_model_readiness import (
    ChatModelReadiness,
    classify_chat_readiness,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.model_catalog_port import ModelCatalogPort


async def count_active_credentials_for_team(
    session: AsyncSession,
    team_id: uuid.UUID | None,
) -> int:
    if team_id is None:
        return 0
    creds = await ProviderCredentialRepository(session).list_for_tenant(team_id)
    return sum(1 for c in creds if c.is_active)


async def compute_chat_readiness(
    session: AsyncSession,
    catalog: ModelCatalogPort,
    *,
    billing: BillingContext,
) -> ChatModelReadiness:
    """根据可请求模型与 active 凭据计算 chat readiness。

    ``total_model_count`` 取连通性无关的已注册 text 模型数，否则当模型全部连通性失败时
    会误判为 needs_model（缺模型），无法落到 needs_connectivity_fix（待修复连通性）。"""
    requestable_ids = await catalog.list_requestable_text_model_ids(
        billing_team_id=billing.team_id,
        user_id=billing.user_id,
    )
    total_model_count = await catalog.count_registered_text_models(
        billing_team_id=billing.team_id,
        user_id=billing.user_id,
    )
    active_creds = await count_active_credentials_for_team(session, billing.team_id)
    return classify_chat_readiness(
        active_credential_count=active_creds,
        requestable_model_count=len(requestable_ids),
        total_model_count=total_model_count,
    )


async def resolve_billing_for_user(
    session: AsyncSession,
    user_id: uuid.UUID | None,
) -> BillingContext:
    return await resolve_billing_context(session, user_id=user_id)


__all__ = [
    "compute_chat_readiness",
    "count_active_credentials_for_team",
    "resolve_billing_for_user",
]
