"""Playground / 调用指南 actor 维度 API（JWT only，无 team 路径）。"""

from __future__ import annotations

from fastapi import APIRouter

from domains.gateway.presentation.credential_response import (
    build_playground_credential_summary_response,
)
from domains.gateway.presentation.schemas.common import PlaygroundCredentialSummaryResponse
from domains.identity.domain.rbac import Role
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid

from ._common import MgmtReads

router = APIRouter()


@router.get(
    "/playground/credential-summaries",
    response_model=list[PlaygroundCredentialSummaryResponse],
)
async def list_playground_credential_summaries(
    current_user: RequiredAuthUser,
    reads: MgmtReads,
) -> list[PlaygroundCredentialSummaryResponse]:
    """跨 membership 聚合个人 + 团队 + 系统凭据摘要（无密钥）。"""
    user_id = get_user_uuid(current_user)
    is_platform_admin = current_user.role == Role.ADMIN.value
    rows = await reads.list_playground_credential_summaries_for_actor(
        user_id,
        is_platform_admin=is_platform_admin,
    )
    creds = [item.credential for item in rows]
    creator_labels = await reads.credential_creator_labels_for(creds)
    return [
        build_playground_credential_summary_response(
            item.credential,
            context_team_id=item.context_team_id,
            creator_label=creator_labels.get(item.credential.id),
        )
        for item in rows
    ]


__all__ = ["router"]
