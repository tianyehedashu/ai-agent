"""
Session Migration Service - 匿名用户 Session 迁移服务

当匿名用户注册或登录后，将其匿名期间创建的 Session 迁移到正式用户账号下。
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging import get_logger

logger = get_logger(__name__)


class SessionMigrationService:
    """Session 迁移服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def migrate_anonymous_sessions(
        self,
        user_id: uuid.UUID | str,
        anonymous_user_id: str,
    ) -> int:
        """将匿名用户的 Session 迁移到正式用户

        Args:
            user_id: 正式用户 ID (UUID 或 UUID 字符串)
            anonymous_user_id: 匿名用户 ID (不含 'anonymous-' 前缀)

        Returns:
            迁移的 Session 数量
        """
        # 确保 user_id 是 UUID 格式
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        # 查找匹配的匿名 Session
        result = await self.db.execute(
            text("""
                UPDATE sessions
                SET user_id = :user_id, anonymous_user_id = NULL
                WHERE anonymous_user_id = :anonymous_user_id
                RETURNING id
            """),
            {"user_id": user_id, "anonymous_user_id": anonymous_user_id},
        )
        migrated_sessions = result.fetchall()
        migrated_count = len(migrated_sessions)

        if migrated_count > 0:
            logger.info(
                "Migrated %d sessions from anonymous user %s to user %s",
                migrated_count,
                anonymous_user_id[:8],
                user_id[:8],
            )

        return migrated_count


async def migrate_anonymous_sessions_on_auth(
    db: AsyncSession,
    user_id: uuid.UUID | str,
    anonymous_user_id: str | None,
) -> int:
    """认证成功后迁移匿名 Session 的便捷函数

    Args:
        db: 数据库会话
        user_id: 正式用户 ID
        anonymous_user_id: 匿名用户 ID（从 Cookie 或 Header 获取）

    Returns:
        迁移的 Session 数量
    """
    if not anonymous_user_id:
        return 0

    service = SessionMigrationService(db)
    return await service.migrate_anonymous_sessions(user_id, anonymous_user_id)
