"""Gateway 鉴权用例组合根工厂。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.identity.application.api_key_use_case import ApiKeyUseCase

from .gateway_access_use_case import GatewayAccessUseCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.identity.application.ports import ApiKeyVerificationPort
    from domains.tenancy.application.ports import TeamResolutionPort
    from libs.iam.tenancy import MembershipPort


def build_gateway_access_use_case(
    session: AsyncSession,
    *,
    membership: MembershipPort | None = None,
    team_resolution: TeamResolutionPort | None = None,
    api_key_verification: ApiKeyVerificationPort | None = None,
) -> GatewayAccessUseCase:
    """装配 GatewayAccessUseCase（默认注入 identity ApiKey 端口实现）。"""
    verifier = api_key_verification or ApiKeyUseCase(session)
    return GatewayAccessUseCase(
        session,
        membership=membership,
        team_resolution=team_resolution,
        api_key_verification=verifier,
    )


__all__ = ["build_gateway_access_use_case"]
