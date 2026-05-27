"""
Session Repository - 会话仓储实现

实现会话数据访问，支持自动权限过滤。
"""

from datetime import UTC, datetime
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.domain.anonymous_tenant import resolve_anonymous_tenant_id
from domains.session.domain.interfaces.session_repository import (
    SessionRepository as SessionRepositoryInterface,
)
from domains.session.infrastructure.models.session import Session
from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.iam.permission_context import get_permission_context


class SessionRepository(TenantScopedRepositoryBase[Session], SessionRepositoryInterface):
    """会话仓储实现（行级过滤走 ``tenant_id`` + ``PermissionContext.team_ids``）。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.db = db

    @property
    def model_class(self) -> type[Session]:
        return Session

    async def _resolve_tenant_id(
        self,
        *,
        user_id: uuid.UUID | None,
        anonymous_user_id: str | None,
    ) -> uuid.UUID:
        teams = PersonalTeamProvisioner(self.db)
        if user_id is not None:
            return await teams.ensure_personal_team(user_id)
        if anonymous_user_id:
            return resolve_anonymous_tenant_id(anonymous_user_id)
        msg = "Either user_id or anonymous_user_id is required to resolve tenant_id"
        raise ValueError(msg)

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        title: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> Session:
        resolved_tenant = tenant_id or await self._resolve_tenant_id(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
        )
        session = Session(
            tenant_id=resolved_tenant,
            agent_id=agent_id,
            title=title,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        return await self.get_in_tenants(session_id)

    async def find_by_user(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Session]:
        ctx = get_permission_context()
        if ctx and not ctx.is_admin:
            if user_id is not None and ctx.user_id != user_id:
                raise ValueError(
                    f"user_id parameter ({user_id}) does not match PermissionContext ({ctx.user_id}). "
                    "This may indicate an authorization bug."
                )
            if anonymous_user_id is not None and ctx.anonymous_user_id != anonymous_user_id:
                raise ValueError(
                    f"anonymous_user_id parameter ({anonymous_user_id}) does not match "
                    f"PermissionContext ({ctx.anonymous_user_id}). "
                    "This may indicate an authorization bug."
                )

        if user_id is not None:
            tenant_id = await self._personal_tenant_id(user_id)
        elif anonymous_user_id:
            tenant_id = resolve_anonymous_tenant_id(anonymous_user_id)
        else:
            msg = "Either user_id or anonymous_user_id is required"
            raise ValueError(msg)

        query = select(self.model_class).where(self.model_class.tenant_id == tenant_id)
        if agent_id is not None:
            query = query.where(self.model_class.agent_id == agent_id)
        order_column = self.model_class.updated_at
        query = query.order_by(order_column.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        session_id: uuid.UUID,
        title: str | None = ...,
        status: str | None = ...,
    ) -> Session | None:
        session = await self.get_by_id(session_id)
        if not session:
            return None

        if title is not ...:
            session.title = title
        if status is not ...:
            session.status = status

        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def update_config(
        self, session_id: uuid.UUID, config_updates: dict, *, flush: bool = True
    ) -> Session | None:
        session = await self.get_by_id(session_id)
        if not session:
            return None

        current = dict(session.config) if session.config else {}
        current.update(config_updates)
        session.config = current

        if flush:
            await self.db.flush()
            await self.db.refresh(session)
        return session

    async def delete(self, session_id: uuid.UUID) -> bool:
        session = await self.get_by_id(session_id)
        if not session:
            return False

        await self.db.delete(session)
        return True

    async def increment_message_count(
        self,
        session_id: uuid.UUID,
        message_count: int = 1,
        token_count: int = 0,
    ) -> None:
        session = await self.get_by_id(session_id)
        if session:
            session.message_count += message_count
            if token_count:
                session.token_count += token_count
            await self.db.flush()

    async def increment_video_task_count(
        self,
        session_id: uuid.UUID,
        count: int = 1,
    ) -> None:
        session = await self.get_by_id(session_id)
        if session:
            session.video_task_count += count
            await self.db.flush()

    async def count_total(self) -> int:
        result = await self.db.execute(select(func.count(Session.id)))
        return result.scalar() or 0

    async def count_active_today(self) -> int:
        today = datetime.now(UTC).date()
        result = await self.db.execute(
            select(func.count(Session.id)).where(func.date(Session.updated_at) == today)
        )
        return result.scalar() or 0

    async def _personal_tenant_id(self, user_id: uuid.UUID) -> uuid.UUID:
        return await PersonalTeamProvisioner(self.db).ensure_personal_team(user_id)

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        tenant_id = await self._personal_tenant_id(user_id)
        result = await self.db.execute(
            select(func.count(Session.id)).where(Session.tenant_id == tenant_id)
        )
        return result.scalar() or 0

    async def sum_tokens_by_user(self, user_id: uuid.UUID) -> int:
        tenant_id = await self._personal_tenant_id(user_id)
        result = await self.db.execute(
            select(func.sum(Session.token_count)).where(Session.tenant_id == tenant_id)
        )
        return result.scalar() or 0

    async def list_ids_by_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        tenant_id = await self._personal_tenant_id(user_id)
        result = await self.db.execute(
            select(Session.id).where(Session.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def reassign_anonymous_to_user(
        self,
        *,
        user_id: uuid.UUID,
        anonymous_user_id: str,
    ) -> int:
        """把匿名 orphan tenant 下的会话迁到正式用户的 personal team。"""
        anon_tenant = resolve_anonymous_tenant_id(anonymous_user_id)
        user_tenant = await self._personal_tenant_id(user_id)
        if anon_tenant == user_tenant:
            return 0
        result = await self.db.execute(
            update(Session)
            .where(Session.tenant_id == anon_tenant)
            .values(tenant_id=user_tenant)
        )
        return result.rowcount or 0
