"""
UserProviderConfigRepository - 用户提供商配置仓储

处理用户 LLM 提供商配置的数据库操作
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.user_provider_config import UserProviderConfig


class UserProviderConfigRepository:
    """用户提供商配置仓储"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_user_and_provider(
        self, user_id: UUID, provider: str
    ) -> UserProviderConfig | None:
        """根据用户ID和提供商获取配置"""
        stmt = select(UserProviderConfig).where(
            UserProviderConfig.user_id == user_id,
            UserProviderConfig.provider == provider,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[UserProviderConfig]:
        """列出用户的所有提供商配置"""
        stmt = (
            select(UserProviderConfig)
            .where(UserProviderConfig.user_id == user_id)
            .order_by(UserProviderConfig.provider)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        user_id: UUID,
        provider: str,
        api_key: str,
        api_base: str | None = None,
        is_active: bool = True,
    ) -> UserProviderConfig:
        """创建或更新提供商配置"""
        # 使用 PostgreSQL 的 ON CONFLICT ... DO UPDATE
        stmt = insert(UserProviderConfig).values(
            user_id=user_id,
            provider=provider,
            api_key=api_key,
            api_base=api_base,
            is_active=is_active,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider"],
            set_={
                "api_key": api_key,
                "api_base": api_base,
                "is_active": is_active,
            },
        ).returning(UserProviderConfig)

        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def delete(self, user_id: UUID, provider: str) -> bool:
        """删除提供商配置"""
        config = await self.get_by_user_and_provider(user_id, provider)
        if config:
            await self._session.delete(config)
            await self._session.flush()
            return True
        return False

    async def update_active_status(
        self, user_id: UUID, provider: str, is_active: bool
    ) -> UserProviderConfig | None:
        """更新配置的激活状态"""
        config = await self.get_by_user_and_provider(user_id, provider)
        if config:
            config.is_active = is_active
            await self._session.flush()
        return config
