"""
UserQuotaRepository - 用户配额仓储

处理用户配额的数据库操作
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.infrastructure.models.quota import QuotaUsageLog, UserQuota


class UserQuotaRepository:
    """用户配额仓储"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_user(self, user_id: UUID) -> UserQuota | None:
        """获取用户配额"""
        stmt = select(UserQuota).where(UserQuota.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[UserQuota]:
        """列出所有用户配额（用于定时重置任务）"""
        stmt = select(UserQuota)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: UUID,
        daily_text_requests: int | None = None,
        daily_image_requests: int | None = None,
        daily_embedding_requests: int | None = None,
        monthly_token_limit: int | None = None,
    ) -> UserQuota:
        """创建用户配额"""
        now = datetime.now(UTC)
        quota = UserQuota(
            user_id=user_id,
            daily_text_requests=daily_text_requests,
            daily_image_requests=daily_image_requests,
            daily_embedding_requests=daily_embedding_requests,
            monthly_token_limit=monthly_token_limit,
            current_daily_text=0,
            current_daily_image=0,
            current_daily_embedding=0,
            current_monthly_tokens=0,
            daily_reset_at=now + timedelta(days=1),
            monthly_reset_at=now + timedelta(days=30),
        )
        self._session.add(quota)
        await self._session.flush()
        return quota

    async def reset_daily_quota(self, user_id: UUID) -> None:
        """重置每日配额"""
        now = datetime.now(UTC)
        stmt = (
            update(UserQuota)
            .where(UserQuota.user_id == user_id)
            .values(
                current_daily_text=0,
                current_daily_image=0,
                current_daily_embedding=0,
                daily_reset_at=now + timedelta(days=1),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def reset_monthly_quota(self, user_id: UUID) -> None:
        """重置每月配额"""
        now = datetime.now(UTC)
        stmt = (
            update(UserQuota)
            .where(UserQuota.user_id == user_id)
            .values(
                current_monthly_tokens=0,
                monthly_reset_at=now + timedelta(days=30),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def increment_usage(self, user_id: UUID, capability: str, amount: int = 1) -> None:
        """递增用量计数"""
        quota = await self.get_by_user(user_id)
        if not quota:
            return

        if capability == "text":
            quota.current_daily_text += amount
        elif capability == "image":
            quota.current_daily_image += amount
        elif capability == "embedding":
            quota.current_daily_embedding += amount

        await self._session.flush()

    async def increment_tokens(self, user_id: UUID, tokens: int) -> None:
        """递增 Token 用量"""
        quota = await self.get_by_user(user_id)
        if quota:
            quota.current_monthly_tokens += tokens
            await self._session.flush()

    async def create_usage_log(
        self,
        user_id: UUID,
        capability: str,
        provider: str,
        model: str | None,
        key_source: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        image_count: int | None = None,
        cost_estimate: float | None = None,
    ) -> QuotaUsageLog:
        """创建用量日志"""
        log = QuotaUsageLog(
            user_id=user_id,
            capability=capability,
            provider=provider,
            model=model,
            key_source=key_source,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            image_count=image_count,
            cost_estimate=cost_estimate,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def get_usage_logs(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[QuotaUsageLog]:
        """获取用量日志"""
        stmt = (
            select(QuotaUsageLog)
            .where(QuotaUsageLog.user_id == user_id)
            .order_by(QuotaUsageLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
