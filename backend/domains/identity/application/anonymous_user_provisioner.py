"""匿名用户 shadow User + personal team（与 cookie 幂等绑定）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.domain.types import ANONYMOUS_ID_PREFIX, Principal
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner

# 匿名账号不可密码登录；占位哈希与测试 fixture 一致，避免 bcrypt 环境差异。
_ANONYMOUS_PLACEHOLDER_HASH = "anonymous-no-login"


class AnonymousUserProvisioner:
    """将 anonymous cookie id 映射为真实 ``users.id``（role=anonymous）。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._teams = PersonalTeamProvisioner(session)

    @staticmethod
    def _normalize_cookie_id(cookie_hash: str) -> str:
        raw = cookie_hash.strip()
        if raw.startswith(ANONYMOUS_ID_PREFIX):
            return Principal.extract_anonymous_id(raw)
        return raw

    async def ensure_shadow_user(self, cookie_hash: str) -> uuid.UUID:
        anon_id = self._normalize_cookie_id(cookie_hash)
        email = Principal.make_anonymous_email(anon_id)
        stmt = select(User).where(User.email == email)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            await self._teams.ensure_personal_team(existing.id)
            return existing.id

        user = User(
            email=email,
            hashed_password=_ANONYMOUS_PLACEHOLDER_HASH,
            is_active=True,
            is_superuser=False,
            is_verified=False,
            name=f"Anonymous ({anon_id[:8]})",
            role="anonymous",
            settings={"anonymous_cookie_id": anon_id},
        )
        self._session.add(user)
        await self._session.flush()
        await self._teams.ensure_personal_team(user.id)
        return user.id

    async def cleanup_anonymous_users(self, retention_days: int = 90) -> int:
        """删除长期未活跃的匿名 shadow 用户（仅 role=anonymous）。"""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        stmt = select(User).where(
            User.role == "anonymous",
            User.created_at < cutoff,
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        for user in rows:
            await self._session.delete(user)
        if rows:
            await self._session.flush()
        return len(rows)


__all__ = ["AnonymousUserProvisioner"]
