"""
Anonymous Data Migration Service - 匿名用户数据迁移服务

当匿名用户注册或登录后，将其匿名期间创建的数据迁移到正式用户账号下。
包括：Session、VideoGenTask。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import text

from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass
class MigrationResult:
    """迁移结果"""

    sessions: int = 0
    video_tasks: int = 0

    @property
    def total(self) -> int:
        return self.sessions + self.video_tasks


class AnonymousDataMigrationService:
    """匿名数据迁移服务

    将匿名用户的 Session 和 VideoGenTask 迁移到正式用户账号。
    仅迁移 user_id IS NULL 的记录，避免重复迁移。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def migrate(
        self,
        user_id: uuid.UUID | str,
        anonymous_user_id: str,
    ) -> MigrationResult:
        """将匿名用户的数据迁移到正式用户

        Args:
            user_id: 正式用户 ID (UUID 或 UUID 字符串)
            anonymous_user_id: 匿名用户 ID (不含 'anonymous-' 前缀)

        Returns:
            MigrationResult 包含各表迁移数量
        """
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        params = {"user_id": user_id, "anonymous_user_id": anonymous_user_id}

        # 迁移 sessions
        session_result = await self.db.execute(
            text("""
                UPDATE sessions
                SET user_id = :user_id, anonymous_user_id = NULL
                WHERE anonymous_user_id = :anonymous_user_id
                  AND user_id IS NULL
                RETURNING id
            """),
            params,
        )
        session_count = len(session_result.fetchall())

        # 迁移 video_gen_tasks
        task_result = await self.db.execute(
            text("""
                UPDATE video_gen_tasks
                SET user_id = :user_id, anonymous_user_id = NULL
                WHERE anonymous_user_id = :anonymous_user_id
                  AND user_id IS NULL
                RETURNING id
            """),
            params,
        )
        task_count = len(task_result.fetchall())

        result = MigrationResult(sessions=session_count, video_tasks=task_count)

        if result.total > 0:
            logger.info(
                "Migrated anonymous data to user %s: %d sessions, %d video_tasks (anonymous_id=%s)",
                str(user_id)[:8],
                result.sessions,
                result.video_tasks,
                anonymous_user_id[:8],
            )

        return result


# 保留向后兼容的别名
SessionMigrationService = AnonymousDataMigrationService


async def migrate_anonymous_data_on_auth(
    db: AsyncSession,
    user_id: uuid.UUID | str,
    anonymous_user_id: str | None,
) -> MigrationResult:
    """认证成功后迁移匿名数据的便捷函数

    在登录或注册时调用，将当前浏览器的匿名数据迁移到正式账号。

    Args:
        db: 数据库会话
        user_id: 正式用户 ID
        anonymous_user_id: 匿名用户 ID（从 Cookie 获取）

    Returns:
        MigrationResult 迁移结果
    """
    if not anonymous_user_id:
        return MigrationResult()

    service = AnonymousDataMigrationService(db)
    return await service.migrate(user_id, anonymous_user_id)


# 向后兼容
async def migrate_anonymous_sessions_on_auth(
    db: AsyncSession,
    user_id: uuid.UUID | str,
    anonymous_user_id: str | None,
) -> int:
    """向后兼容的迁移函数"""
    result = await migrate_anonymous_data_on_auth(db, user_id, anonymous_user_id)
    return result.sessions
