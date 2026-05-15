"""
API Key Use Case - API Key 用例

编排 API Key 相关的操作，包括 CRUD、验证、审计日志。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.identity.domain.api_key_types import (
    ApiKeyCreateRequest,
    ApiKeyEntity,
    ApiKeyGatewayGrantEntity,
    ApiKeyGatewayGrantRequest,
    ApiKeyScope,
    ApiKeyUpdateRequest,
    ApiKeyUsageLogResponse,
)
from domains.identity.domain.services.api_key_service import (
    ApiKeyDomainService,
    ApiKeyGenerator,
)
from domains.identity.infrastructure.repositories.api_key_repository import (
    ApiKeyRepository,
)
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository
from libs.exceptions import NotFoundError, ValidationError
from libs.iam.tenancy import TenantId

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.identity.infrastructure.models.api_key import ApiKey, ApiKeyGatewayGrant


class ApiKeyUseCase:
    """API Key 用例

    编排 API Key 相关的操作，包括 CRUD、验证、审计日志。
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: ApiKeyRepository | None = None,
        generator: ApiKeyGenerator | None = None,
        encryption_key: str | None = None,
    ) -> None:
        self.db = db
        self.repo = repo or ApiKeyRepository(db)
        self.generator = generator or ApiKeyGenerator(encryption_key)
        self.domain_service = ApiKeyDomainService(self.generator)
        self._encryption_key = encryption_key
        self._teams = TeamRepository(db)
        self._membership = TenancyMembershipAdapter()

    # =======================================================================
    # CRUD 操作
    # =======================================================================

    async def create_api_key(
        self,
        user_id: uuid.UUID,
        request: ApiKeyCreateRequest,
    ) -> tuple[ApiKeyEntity, str]:
        """创建 API Key

        Args:
            user_id: 用户 ID
            request: 创建请求

        Returns:
            (entity, plain_key) - 实体和完整密钥（仅此机会返回）
        """
        # 验证并生成
        expires_at, scopes = self.domain_service.validate_creation_request(
            name=request.name,
            description=request.description,
            scopes=set(request.scopes) if request.scopes else None,
            expires_in_days=request.expires_in_days,
        )
        plain_key, key_id, key_hash = self.generator.generate()

        # 加密完整 Key（用于后续查看）
        if not self._encryption_key:
            raise ValidationError("API key encryption is not configured")

        encrypted_key = self.generator.encrypt_key(plain_key, self._encryption_key)

        # 创建记录
        model = await self.repo.create(
            user_id=user_id,
            key_hash=key_hash,
            key_id=key_id,
            key_prefix="sk_",
            name=request.name,
            description=request.description,
            scopes=scopes,
            expires_at=expires_at,
            encrypted_key=encrypted_key,
        )

        grants = await self._validated_gateway_grants(
            user_id=user_id,
            scopes=scopes,
            requested=request.gateway_grants,
        )
        grant_models = (
            await self.repo.replace_gateway_grants(
                api_key_id=model.id,
                user_id=user_id,
                grants=grants,
            )
            if grants
            else []
        )

        entity = self._to_entity(model, grant_models)
        return entity, plain_key

    async def get_api_key(
        self,
        api_key_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ApiKeyEntity:
        """获取 API Key

        Args:
            api_key_id: API Key ID
            user_id: 用户 ID

        Returns:
            API Key 实体

        Raises:
            NotFoundError: API Key 不存在或无权限访问
        """
        model = await self.repo.get_by_id(api_key_id)
        if not model:
            raise NotFoundError("ApiKey", str(api_key_id))

        # 验证所有权（Repository 已通过 PermissionContext 自动处理）
        grants = await self.repo.list_gateway_grants(api_key_id)
        return self._to_entity(model, grants)

    async def list_api_keys(
        self,
        user_id: uuid.UUID,
        include_expired: bool = False,
        include_revoked: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> list[ApiKeyEntity]:
        """列出用户的 API Key

        Args:
            user_id: 用户 ID
            include_expired: 是否包含已过期的 Key
            include_revoked: 是否包含已撤销的 Key
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            API Key 实体列表
        """
        models = await self.repo.find_by_user(
            user_id=user_id,
            include_expired=include_expired,
            include_revoked=include_revoked,
            skip=skip,
            limit=limit,
        )
        out: list[ApiKeyEntity] = []
        for model in models:
            grants = await self.repo.list_gateway_grants(model.id)
            out.append(self._to_entity(model, grants))
        return out

    async def update_api_key(
        self,
        api_key_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ApiKeyUpdateRequest,
    ) -> ApiKeyEntity:
        """更新 API Key

        Args:
            api_key_id: API Key ID
            user_id: 用户 ID
            request: 更新请求

        Returns:
            更新后的 API Key 实体

        Raises:
            NotFoundError: API Key 不存在或无权限访问
            ValidationError: 更新数据验证失败
        """
        # 先获取当前实体（验证所有权）
        current = await self.get_api_key(api_key_id, user_id)

        # 计算新的过期时间
        expires_at = current.expires_at
        if request.extend_expiry_days:
            try:
                expires_at = self.domain_service.validate_expiry_update(
                    current.expires_at,
                    request.extend_expiry_days,
                )
            except ValueError as e:
                raise ValidationError(str(e)) from e

        # 转换作用域
        scopes = None
        if request.scopes is not None:
            scopes = set(request.scopes)

        # 更新
        model = await self.repo.update(
            api_key_id=api_key_id,
            name=request.name,
            description=request.description,
            scopes=scopes,
            expires_at=expires_at,
        )

        if model is None:
            raise NotFoundError("ApiKey", str(api_key_id))

        grant_models = await self.repo.list_gateway_grants(api_key_id)
        if request.gateway_grants is not None or scopes is not None:
            effective_scopes = scopes if scopes is not None else current.scopes
            if request.gateway_grants is not None:
                requested_grants = request.gateway_grants
            elif ApiKeyScope.GATEWAY_PROXY in effective_scopes:
                requested_grants = [
                    self._grant_request_from_entity(grant) for grant in current.gateway_grants
                ]
            else:
                requested_grants = []
            grants = await self._validated_gateway_grants(
                user_id=user_id,
                scopes=effective_scopes,
                requested=requested_grants,
            )
            grant_models = await self.repo.replace_gateway_grants(
                api_key_id=api_key_id,
                user_id=user_id,
                grants=grants,
            )

        return self._to_entity(model, grant_models)

    async def revoke_api_key(
        self,
        api_key_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """撤销 API Key

        Args:
            api_key_id: API Key ID
            user_id: 用户 ID

        Raises:
            NotFoundError: API Key 不存在或无权限访问
        """
        # 先验证所有权
        await self.get_api_key(api_key_id, user_id)

        await self.repo.update(api_key_id, is_active=False)

    async def delete_api_key(
        self,
        api_key_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """删除 API Key

        Args:
            api_key_id: API Key ID
            user_id: 用户 ID

        Raises:
            NotFoundError: API Key 不存在或无权限访问
        """
        # 先验证所有权
        await self.get_api_key(api_key_id, user_id)

        await self.repo.delete(api_key_id)

    # =======================================================================
    # 验证
    # =======================================================================

    async def reveal_api_key(
        self,
        api_key_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str:
        """解密并显示完整的 API Key

        Args:
            api_key_id: API Key ID
            user_id: 用户 ID

        Returns:
            完整的 API Key（明文）

        Raises:
            NotFoundError: API Key 不存在或无权限访问
            ValidationError: 未配置加密密钥或无法解密
        """
        if not self._encryption_key:
            raise ValidationError("API key reveal is not configured")

        # 验证所有权
        await self.get_api_key(api_key_id, user_id)

        # 获取加密的 Key
        encrypted_key = await self.repo.get_encrypted_key(api_key_id)

        try:
            plain_key = self.generator.decrypt_key(encrypted_key, self._encryption_key)
            return plain_key
        except Exception as e:
            raise ValidationError("Failed to decrypt API key") from e

    # =======================================================================
    # 验证（原有方法）
    # =======================================================================

    async def verify_api_key(
        self,
        plain_key: str,
    ) -> ApiKeyEntity | None:
        """验证 API Key

        Args:
            plain_key: 完整的 API Key

        Returns:
            验证成功返回实体，失败返回 None
        """
        # 检查格式
        if not self.domain_service.is_valid_key_format(plain_key):
            return None

        # 提取 key_id（用于加速查找）
        parts = plain_key.split("_")
        if len(parts) != 3:
            return None
        key_id = parts[1]

        # 查找所有匹配 key_id 的记录
        candidates = await self.repo.get_by_key_id(key_id)

        # 逐个验证哈希
        for model in candidates:
            if self.generator.verify_key(plain_key, model.key_hash):
                grants = await self.repo.list_gateway_grants(model.id)
                entity = self._to_entity(model, grants)
                # 返回实体（调用方需要检查 is_valid 判断是否过期/撤销）
                return entity

        return None

    # =======================================================================
    # 使用日志
    # =======================================================================

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
        """记录 API Key 使用

        Args:
            api_key_id: API Key ID
            endpoint: 请求端点
            method: HTTP 方法
            ip_address: 客户端 IP
            user_agent: User-Agent
            status_code: HTTP 状态码
            response_time_ms: 响应时间（毫秒）
        """
        await self.repo.record_usage(api_key_id)
        await self.repo.create_usage_log(
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
            response_time_ms=response_time_ms,
        )

    async def get_usage_logs(
        self,
        api_key_id: uuid.UUID,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ApiKeyUsageLogResponse], int]:
        """获取使用日志

        Args:
            api_key_id: API Key ID
            user_id: 用户 ID
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            (日志列表, 总数)
        """
        # 先验证所有权
        await self.get_api_key(api_key_id, user_id)

        logs = await self.repo.get_usage_logs(api_key_id, skip, limit)
        total = await self.repo.count_usage_logs(api_key_id)

        response_list = [
            ApiKeyUsageLogResponse(
                id=str(log.id),
                endpoint=log.endpoint,
                method=log.method,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                status_code=log.status_code,
                response_time_ms=log.response_time_ms,
                created_at=log.created_at,
            )
            for log in logs
        ]

        return response_list, total

    # =======================================================================
    # 辅助方法
    # =======================================================================

    async def _validated_gateway_grants(
        self,
        *,
        user_id: uuid.UUID,
        scopes: set[ApiKeyScope],
        requested: list[ApiKeyGatewayGrantRequest],
    ) -> list[ApiKeyGatewayGrantRequest]:
        """验证并规范化 Gateway grants。

        ``gateway:proxy`` 没有显式 grant 时只默认授予 personal team，避免一把平台
        Key 能在用户加入的所有团队间任意切换。
        """
        if ApiKeyScope.GATEWAY_PROXY not in scopes:
            if requested:
                raise ValidationError("gateway_grants require scope gateway:proxy")
            return []

        grants = list(requested)
        if not grants:
            personal = await self._teams.get_personal(user_id)
            if personal is None or not personal.is_active:
                raise ValidationError(
                    "gateway:proxy API key requires a personal team or explicit gateway_grants"
                )
            grants = [ApiKeyGatewayGrantRequest(team_id=personal.id)]

        seen: set[uuid.UUID] = set()
        for grant in grants:
            if grant.team_id in seen:
                raise ValidationError(f"duplicate gateway grant team_id: {grant.team_id}")
            seen.add(grant.team_id)
            team = await self._teams.get(grant.team_id)
            if team is None or not team.is_active:
                raise ValidationError(f"gateway grant team not found: {grant.team_id}")
            role = await self._membership.member_role(
                self.db,
                tenant_id=TenantId(grant.team_id),
                user_id=user_id,
            )
            if role not in {"owner", "admin"}:
                raise ValidationError(
                    f"gateway grant requires team owner/admin role: {grant.team_id}"
                )
        return grants

    @staticmethod
    def _grant_request_from_entity(
        grant: ApiKeyGatewayGrantEntity,
    ) -> ApiKeyGatewayGrantRequest:
        return ApiKeyGatewayGrantRequest(
            team_id=grant.team_id,
            allowed_models=list(grant.allowed_models),
            allowed_capabilities=list(grant.allowed_capabilities),
            rpm_limit=grant.rpm_limit,
            tpm_limit=grant.tpm_limit,
            store_full_messages=grant.store_full_messages,
            guardrail_enabled=grant.guardrail_enabled,
        )

    def _grant_to_entity(self, model: ApiKeyGatewayGrant) -> ApiKeyGatewayGrantEntity:
        return ApiKeyGatewayGrantEntity(
            id=model.id,
            api_key_id=model.api_key_id,
            user_id=model.user_id,
            team_id=model.team_id,
            allowed_models=tuple(model.allowed_models or ()),
            allowed_capabilities=tuple(model.allowed_capabilities or ()),
            rpm_limit=model.rpm_limit,
            tpm_limit=model.tpm_limit,
            store_full_messages=model.store_full_messages,
            guardrail_enabled=model.guardrail_enabled,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_entity(
        self,
        model: ApiKey,
        gateway_grants: list[ApiKeyGatewayGrant] | None = None,
    ) -> ApiKeyEntity:
        """ORM 模型转领域实体

        Args:
            model: ORM 模型

        Returns:
            领域实体
        """
        return ApiKeyEntity(
            id=model.id,
            user_id=model.user_id,
            key_hash=model.key_hash,
            key_id=model.key_id,
            key_prefix=model.key_prefix,
            name=model.name,
            description=model.description,
            scopes={ApiKeyScope(s) for s in model.scopes},
            expires_at=model.expires_at,
            is_active=model.is_active,
            last_used_at=model.last_used_at,
            usage_count=model.usage_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            gateway_grants=tuple(
                self._grant_to_entity(grant)
                for grant in (gateway_grants if isinstance(gateway_grants, list) else [])
            ),
        )
