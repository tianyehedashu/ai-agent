"""Playground / 调用指南凭据聚合读侧（actor 维度，跨 membership 团队）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.tenancy.application.ports import GatewayTeamListingPort
from domains.tenancy.application.team_service import TeamService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.management.reads import GatewayManagementReadService


@dataclass(frozen=True)
class PlaygroundCredentialSummaryItem:
    credential: CredentialReadModel
    context_team_id: uuid.UUID | None


async def list_playground_credential_summaries_for_actor(
    session: AsyncSession,
    reads: GatewayManagementReadService,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    team_listing: GatewayTeamListingPort | None = None,
) -> list[PlaygroundCredentialSummaryItem]:
    """聚合 user 凭据 + 各 membership 团队 summaries（含 system），按 id 去重。"""
    listing = team_listing or TeamService(session)
    # Playground 始终 membership-only（与前端 gateway-team store / membership_only 对齐），
    # 避免平台 admin 聚合全站 personal/协作团队凭据导致下拉出现不可选项。
    memberships = await listing.list_gateway_team_memberships(
        user_id,
        is_platform_admin=False,
    )
    personal_team_id = next(
        (m.team_id for m in memberships if m.kind == "personal"),
        None,
    )

    by_id: dict[uuid.UUID, PlaygroundCredentialSummaryItem] = {}

    for cred in await reads.list_user_credentials(user_id):
        if not cred.is_active:
            continue
        by_id[cred.id] = PlaygroundCredentialSummaryItem(
            credential=cred,
            context_team_id=personal_team_id,
        )

    for membership in memberships:
        rows = await reads.list_credential_summaries_for_team(
            membership.team_id,
            user_id=user_id,
            is_platform_admin=is_platform_admin,
        )
        for cred in rows:
            if not cred.is_active:
                continue
            if cred.scope == "user":
                continue
            if cred.id in by_id:
                continue
            by_id[cred.id] = PlaygroundCredentialSummaryItem(
                credential=cred,
                context_team_id=membership.team_id,
            )

    return list(by_id.values())


__all__ = [
    "PlaygroundCredentialSummaryItem",
    "list_playground_credential_summaries_for_actor",
]
