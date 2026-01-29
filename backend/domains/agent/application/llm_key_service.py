"""
LLM Key Service - LLM Key 选择与配额管理服务

职责:
1. 选择 API Key（用户 Key 优先，回退到系统 Key）
2. 配额检查与扣减
3. 用量日志记录

设计原则:
- 用户配置了自己的 Key → 无限制
- 使用系统 Key → 受配额限制
"""

from typing import Protocol
from uuid import UUID

from exceptions import AIAgentError


class NoKeyConfiguredError(AIAgentError):
    """未配置 API Key 错误"""

    def __init__(self, provider: str):
        super().__init__(f"未配置 {provider} 的 API Key")
        self.provider = provider


class QuotaExceededError(AIAgentError):
    """配额超限错误"""

    def __init__(self, capability: str, limit: int, used: int):
        super().__init__(f"{capability} 配额已用尽：限制 {limit}，已用 {used}")
        self.capability = capability
        self.limit = limit
        self.used = used


class EncryptorProtocol(Protocol):
    """加解密协议"""

    def encrypt(self, plaintext: str) -> str:
        """加密"""
        ...

    def decrypt(self, ciphertext: str) -> str:
        """解密"""
        ...


class UserProviderConfigRepositoryProtocol(Protocol):
    """用户提供商配置仓储协议"""

    async def get_by_user_and_provider(
        self, user_id: UUID, provider: str
    ) -> "UserProviderConfigProtocol | None":
        """根据用户ID和提供商获取配置"""
        ...


class UserProviderConfigProtocol(Protocol):
    """用户提供商配置协议"""

    api_key: str
    api_base: str | None
    is_active: bool


class UserQuotaRepositoryProtocol(Protocol):
    """用户配额仓储协议"""

    async def get_by_user(self, user_id: UUID) -> "UserQuotaProtocol | None":
        """获取用户配额"""
        ...

    async def reset_daily_quota(self, user_id: UUID) -> None:
        """重置每日配额"""
        ...

    async def increment_usage(self, user_id: UUID, capability: str, amount: int = 1) -> None:
        """递增用量计数"""
        ...

    async def increment_tokens(self, user_id: UUID, tokens: int) -> None:
        """递增 Token 用量"""
        ...

    async def create_usage_log(self, **kwargs) -> None:
        """创建用量日志"""
        ...


class UserQuotaProtocol(Protocol):
    """用户配额协议"""

    daily_text_requests: int | None
    daily_image_requests: int | None
    daily_embedding_requests: int | None
    monthly_token_limit: int | None
    current_daily_text: int
    current_daily_image: int
    current_daily_embedding: int
    current_monthly_tokens: int

    def needs_daily_reset(self) -> bool:
        """是否需要重置每日配额"""
        ...


class LLMConfigProtocol(Protocol):
    """LLM 配置协议"""

    def get_provider_api_key(self, provider: str) -> str | None:
        """获取提供商的系统 API Key"""
        ...

    def get_provider_api_base(self, provider: str) -> str | None:
        """获取提供商的 API Base"""
        ...

    default_daily_text_requests: int
    default_daily_image_requests: int
    default_daily_embedding_requests: int


class LLMKeyService:
    """LLM Key 选择与配额管理服务

    使用流程:
    1. get_provider_config() - 获取 API Key
    2. 如果 key_source == "system":
       - check_quota() - 检查配额
       - deduct_quota() - 扣减配额（调用成功后）
    3. record_usage() - 记录用量日志
    """

    def __init__(
        self,
        provider_repo: UserProviderConfigRepositoryProtocol,
        quota_repo: UserQuotaRepositoryProtocol,
        config: LLMConfigProtocol,
        encryptor: EncryptorProtocol,
    ):
        self._provider_repo = provider_repo
        self._quota_repo = quota_repo
        self._config = config
        self._encryptor = encryptor

    async def get_provider_config(
        self, user_id: UUID, provider: str
    ) -> tuple[str, str | None, str]:
        """获取指定提供商的 API Key 配置

        Args:
            user_id: 用户 ID
            provider: 提供商标识 (openai, dashscope, etc.)

        Returns:
            (api_key, api_base, key_source)
            - api_key: API Key（已解密）
            - api_base: API Base URL（可能为 None）
            - key_source: "user" 或 "system"

        Raises:
            NoKeyConfiguredError: 无可用 Key
        """
        # 1. 尝试获取用户配置的 Key
        user_config = await self._provider_repo.get_by_user_and_provider(user_id, provider)

        if user_config and user_config.is_active:
            # 用户配置了有效的 Key
            decrypted_key = self._encryptor.decrypt(user_config.api_key)
            return (decrypted_key, user_config.api_base, "user")

        # 2. 回退到系统 Key
        system_key = self._config.get_provider_api_key(provider)
        if system_key:
            system_base = self._config.get_provider_api_base(provider)
            return (system_key, system_base, "system")

        # 3. 无可用 Key
        raise NoKeyConfiguredError(provider)

    async def check_quota(self, user_id: UUID, capability: str) -> None:
        """检查用户配额是否足够

        Args:
            user_id: 用户 ID
            capability: 能力类型 (text, image, embedding)

        Raises:
            QuotaExceededError: 配额超限
        """
        quota = await self._quota_repo.get_by_user(user_id)

        if quota is None:
            # 无配额记录，使用默认配额（允许通过）
            return

        # 检查是否需要重置每日配额
        if quota.needs_daily_reset():
            await self._quota_repo.reset_daily_quota(user_id)
            return  # 重置后配额充足

        # 获取对应能力的配额限制和当前用量
        limit, used = self._get_quota_for_capability(quota, capability)

        if limit is None:
            # 无限制
            return

        if used >= limit:
            raise QuotaExceededError(capability, limit, used)

    def _get_quota_for_capability(
        self, quota: UserQuotaProtocol, capability: str
    ) -> tuple[int | None, int]:
        """获取指定能力的配额限制和当前用量"""
        quota_map = {
            "text": (quota.daily_text_requests, quota.current_daily_text),
            "image": (quota.daily_image_requests, quota.current_daily_image),
            "embedding": (quota.daily_embedding_requests, quota.current_daily_embedding),
        }
        return quota_map.get(capability, (None, 0))

    async def deduct_quota(
        self,
        user_id: UUID,
        capability: str,
        amount: int = 1,
        tokens: int | None = None,
    ) -> None:
        """扣减配额

        Args:
            user_id: 用户 ID
            capability: 能力类型
            amount: 请求次数（默认 1）
            tokens: Token 数量（可选）
        """
        await self._quota_repo.increment_usage(user_id, capability, amount=amount)

        if tokens:
            await self._quota_repo.increment_tokens(user_id, tokens=tokens)

    async def record_usage(
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
    ) -> None:
        """记录用量日志

        无论使用用户 Key 还是系统 Key，都会记录用量。
        """
        await self._quota_repo.create_usage_log(
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
