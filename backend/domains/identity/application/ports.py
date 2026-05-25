"""Identity application ports.

Ports declared here are the public application-layer contracts offered by the
identity domain to other bounded contexts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    import uuid

    from domains.identity.domain.api_key_types import ApiKeyEntity


@dataclass(frozen=True, slots=True)
class UserSummaryView:
    """跨域用户摘要（不含敏感字段）。"""

    name: str | None
    email: str


def user_display_label(summary: UserSummaryView | None) -> str | None:
    """展示用标签：优先 name，否则 email。"""
    if summary is None:
        return None
    if summary.name and summary.name.strip():
        return summary.name.strip()
    stripped_email = summary.email.strip()
    return stripped_email or None


class UserSummaryQueryPort(Protocol):
    """按用户 ID 批量查询展示摘要（Gateway 日志标签、metadata snapshot 等）。"""

    async def list_summary_views_by_ids(
        self, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, UserSummaryView]:
        ...


class IdentityApplicationPort(Protocol):
    """Identity application capabilities exposed cross-domain."""

    async def count_users(self) -> int:
        """Count registered users."""
        ...


class ApiKeyVerificationPort(Protocol):
    """平台 sk-* 验签（Gateway 代理入站）。"""

    async def verify_api_key(self, plain_key: str) -> ApiKeyEntity | None:
        """验证 API Key，成功返回实体（含 gateway_grants），失败返回 None。"""
        ...

    async def record_usage(
        self,
        api_key_id: uuid.UUID,
        endpoint: str,
        method: str,
        ip_address: str | None,
        user_agent: str | None,
        status_code: int,
        response_time_ms: int | None,
    ) -> None:
        """记录 API Key 使用（Gateway 代理完成后回写）。"""
        ...


class ApiKeyGatewayGrantQueryPort(Protocol):
    """Gateway 管理面对 api_key_gateway_grants 的归属校验。"""

    async def assert_gateway_grant_in_team(
        self,
        grant_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        """grant 存在且属于团队（或平台管理员）。"""
        ...


__all__ = [
    "ApiKeyGatewayGrantQueryPort",
    "ApiKeyVerificationPort",
    "IdentityApplicationPort",
    "UserSummaryQueryPort",
    "UserSummaryView",
    "user_display_label",
]
