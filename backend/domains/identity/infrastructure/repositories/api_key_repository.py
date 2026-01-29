"""
API Key Repository - API Key 仓储实现

实现 API Key 数据访问，支持自动权限过滤。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from domains.identity.infrastructure.models.api_key import ApiKey, ApiKeyUsageLog
from libs.db.base_repository import OwnedRepositoryBase
from libs.db.permission_context import get_permission_context

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.identity.domain.api_key_types import ApiKeyScope


class ApiKeyRepository(OwnedRepositoryBase[ApiKey]):
    """API Key 仓储实现

    继承 OwnedRepositoryBase 提供自动权限过滤功能。
    仅支持注册用户。
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.db = db

    @property
    def model_class(self) -> type[ApiKey]:
        """返回模型类"""
        return ApiKey

    # 不支持匿名用户，使用默认的 anonymous_user_id_column = None

    async def create(
        self,
        user_id: uuid.UUID,
        key_hash: str,
        key_id: str,
        key_prefix: str,
        name: str,
        description: str | None,
        scopes: set[ApiKeyScope],
        expires_at: datetime,
        encrypted_key: str,
    ) -> ApiKey:
        """创建 API Key

        Args:
            user_id: 所属用户 ID
            key_hash: 哈希后的 Key
            key_id: 标识符
            key_prefix: 前缀
            name: 名称
            description: 描述
            scopes: 作用域集合
            expires_at: 过期时间
            encrypted_key: 加密后的完整 Key（用于后续查看）

        Returns:
            创建的 ApiKey 模型
        """
        api_key = ApiKey(
            user_id=user_id,
            key_hash=key_hash,
            key_id=key_id,
            key_prefix=key_prefix,
            name=name,
            description=description,
            scopes=[s.value for s in scopes],
            expires_at=expires_at,
            encrypted_key=encrypted_key,
        )
        self.db.add(api_key)
        await self.db.flush()
        await self.db.refresh(api_key)
        return api_key

    async def get_by_id(self, api_key_id: uuid.UUID) -> ApiKey | None:
        """通过 ID 获取 API Key（自动检查所有权）"""
        return await self.get_owned(api_key_id)

    async def get_encrypted_key(self, api_key_id: uuid.UUID) -> str:
        """获取加密的完整 Key

        Args:
            api_key_id: API Key ID

        Returns:
            加密的完整 Key
        """
        api_key = await self.get_by_id(api_key_id)
        if not api_key:
            raise ValueError("API Key not found")
        return api_key.encrypted_key

    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        """通过 key_hash 获取 API Key（验证用）

        注意：此方法不进行所有权过滤，用于 API Key 认证。
        """
        query = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_key_id(self, key_id: str) -> list[ApiKey]:
        """通过 key_id 获取 API Key 列表（用于验证时的加速查找）

        注意：此方法不进行所有权过滤，用于 API Key 认证。
        """
        query = select(ApiKey).where(ApiKey.key_id == key_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def find_by_user(
        self,
        user_id: uuid.UUID,
        include_expired: bool = False,
        include_revoked: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> list[ApiKey]:
        """查询用户的 API Key 列表

        Args:
            user_id: 注册用户 ID（必须与 PermissionContext 一致）
            include_expired: 是否包含已过期的 Key
            include_revoked: 是否包含已撤销的 Key
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            ApiKey 模型列表
        """
        # 验证传递的参数与 PermissionContext 一致（防止授权漏洞）
        ctx = get_permission_context()
        if ctx and not ctx.is_admin and ctx.user_id != user_id:
            raise ValueError(
                f"user_id parameter ({user_id}) does not match PermissionContext ({ctx.user_id}). "
                "This may indicate an authorization bug."
            )

        # 使用 find_owned 自动应用权限过滤
        query = select(self.model_class)
        query = self._apply_ownership_filter(query)

        # 应用状态过滤
        if not include_expired:
            query = query.where(ApiKey.expires_at > datetime.now())
        if not include_revoked:
            query = query.where(ApiKey.is_active.is_(True))

        # 排序和分页
        query = query.order_by(ApiKey.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        api_key_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        scopes: set[ApiKeyScope] | None = None,
        is_active: bool | None = None,
        expires_at: datetime | None = None,
    ) -> ApiKey | None:
        """更新 API Key

        Args:
            api_key_id: API Key ID
            name: 新名称
            description: 新描述
            scopes: 新作用域
            is_active: 激活状态
            expires_at: 新过期时间

        Returns:
            更新后的 ApiKey 或 None
        """
        api_key = await self.get_by_id(api_key_id)
        if not api_key:
            return None

        if name is not None:
            api_key.name = name
        if description is not None:
            api_key.description = description
        if scopes is not None:
            api_key.scopes = [s.value for s in scopes]
        if is_active is not None:
            api_key.is_active = is_active
        if expires_at is not None:
            api_key.expires_at = expires_at

        await self.db.flush()
        await self.db.refresh(api_key)
        return api_key

    async def record_usage(
        self,
        api_key_id: uuid.UUID,
    ) -> None:
        """记录 API Key 使用

        Args:
            api_key_id: API Key ID
        """
        api_key = await self.get_by_id(api_key_id)
        if api_key:
            api_key.last_used_at = datetime.now()
            api_key.usage_count += 1
            await self.db.flush()

    async def delete(self, api_key_id: uuid.UUID) -> bool:
        """删除 API Key

        Args:
            api_key_id: API Key ID

        Returns:
            是否删除成功
        """
        api_key = await self.get_by_id(api_key_id)
        if not api_key:
            return False

        await self.db.delete(api_key)
        return True

    # =======================================================================
    # Usage Logs
    # =======================================================================

    async def create_usage_log(
        self,
        api_key_id: uuid.UUID,
        endpoint: str,
        method: str,
        ip_address: str | None,
        user_agent: str | None,
        status_code: int,
        response_time_ms: int | None,
    ) -> ApiKeyUsageLog:
        """创建使用日志

        Args:
            api_key_id: API Key ID
            endpoint: 请求端点
            method: HTTP 方法
            ip_address: 客户端 IP
            user_agent: User-Agent
            status_code: HTTP 状态码
            response_time_ms: 响应时间（毫秒）

        Returns:
            创建的 ApiKeyUsageLog
        """
        log = ApiKeyUsageLog(
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
            response_time_ms=response_time_ms,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def get_usage_logs(
        self,
        api_key_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ApiKeyUsageLog]:
        """获取 API Key 的使用日志

        Args:
            api_key_id: API Key ID
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            ApiKeyUsageLog 列表
        """
        # 先验证所有权（确保当前用户有权限访问此 API Key）
        await self.get_by_id(api_key_id)

        query = (
            select(ApiKeyUsageLog)
            .where(ApiKeyUsageLog.api_key_id == api_key_id)
            .order_by(ApiKeyUsageLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_usage_logs(self, api_key_id: uuid.UUID) -> int:
        """统计使用日志数量

        Args:
            api_key_id: API Key ID

        Returns:
            日志数量
        """
        # 先验证所有权
        await self.get_by_id(api_key_id)

        query = (
            select(func.count())
            .select_from(ApiKeyUsageLog)
            .where(ApiKeyUsageLog.api_key_id == api_key_id)
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
