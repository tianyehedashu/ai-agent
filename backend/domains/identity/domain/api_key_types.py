"""
API Key Domain Types - API Key 领域类型定义

包含:
- ApiKeyScope: 作用域枚举
- ApiKeyStatus: 状态枚举
- ApiKeyFormat: 格式常量
- ApiKeyEntity: API Key 实体
- Request/Response DTO
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import uuid  # noqa: TC003 - Pydantic resolves deferred uuid.UUID annotations at runtime.

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# ApiKeyScope - 作用域枚举
# =============================================================================


class ApiKeyScope(str, Enum):
    """API Key 作用域

    定义 API Key 可访问的资源范围，实现最小权限原则。
    与 RBAC Permission 保持一致的命名风格。
    """

    # Agent 操作
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:update"  # 写权限对应 update
    AGENT_EXECUTE = "agent:execute"

    # Session 操作
    SESSION_READ = "session:read"
    SESSION_WRITE = "session:create"
    SESSION_DELETE = "session:delete"

    # Memory 操作
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"

    # Workflow 操作
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:update"

    # 系统操作
    SYSTEM_READ = "system:read"

    # MCP 服务器访问
    MCP_LLM_SERVER = "mcp:llm-server"  # LLM 服务器访问
    MCP_FILESYSTEM_SERVER = "mcp:filesystem-server"  # 文件系统服务器
    MCP_MEMORY_SERVER = "mcp:memory-server"  # 记忆系统服务器
    MCP_WORKFLOW_SERVER = "mcp:workflow-server"  # 工作流服务器
    MCP_CUSTOM_SERVER = "mcp:custom-server"  # 自定义服务器
    MCP_ALL_SERVERS = "mcp:all"  # 所有 MCP 服务器

    # AI Gateway 访问
    GATEWAY_PROXY = "gateway:proxy"  # 调用 OpenAI 兼容入口 /v1/*
    GATEWAY_ADMIN = "gateway:admin"  # 管理团队/Key/路由/预算
    GATEWAY_READ = "gateway:read"  # 只读仪表盘/日志


# 作用域分组（便于快速设置常用组合）
API_KEY_SCOPE_GROUPS: dict[str, set[ApiKeyScope]] = {
    "read_only": {
        ApiKeyScope.AGENT_READ,
        ApiKeyScope.SESSION_READ,
        ApiKeyScope.MEMORY_READ,
        ApiKeyScope.WORKFLOW_READ,
        ApiKeyScope.SYSTEM_READ,
    },
    "full_access": {
        ApiKeyScope.AGENT_READ,
        ApiKeyScope.AGENT_WRITE,
        ApiKeyScope.AGENT_EXECUTE,
        ApiKeyScope.SESSION_READ,
        ApiKeyScope.SESSION_WRITE,
        ApiKeyScope.SESSION_DELETE,
        ApiKeyScope.MEMORY_READ,
        ApiKeyScope.MEMORY_WRITE,
        ApiKeyScope.WORKFLOW_READ,
        ApiKeyScope.WORKFLOW_WRITE,
        ApiKeyScope.SYSTEM_READ,
    },
    "agent_only": {
        ApiKeyScope.AGENT_READ,
        ApiKeyScope.AGENT_EXECUTE,
        ApiKeyScope.SESSION_READ,
        ApiKeyScope.SESSION_WRITE,
    },
    "mcp_llm_only": {
        ApiKeyScope.MCP_LLM_SERVER,
    },
    "mcp_all": {
        ApiKeyScope.MCP_LLM_SERVER,
        ApiKeyScope.MCP_FILESYSTEM_SERVER,
        ApiKeyScope.MCP_MEMORY_SERVER,
        ApiKeyScope.MCP_WORKFLOW_SERVER,
        ApiKeyScope.MCP_CUSTOM_SERVER,
    },
    "mcp_full": {
        ApiKeyScope.MCP_ALL_SERVERS,
    },
    "gateway_proxy": {
        ApiKeyScope.GATEWAY_PROXY,
    },
    "gateway_full": {
        ApiKeyScope.GATEWAY_PROXY,
        ApiKeyScope.GATEWAY_ADMIN,
        ApiKeyScope.GATEWAY_READ,
    },
}


GATEWAY_PROXY_CAPABILITY_VALUES: frozenset[str] = frozenset(
    {
        "chat",
        "embedding",
        "image",
        "audio_transcription",
        "audio_speech",
        "rerank",
        "video_generation",
        "moderation",
    }
)


# =============================================================================
# ApiKeyStatus - 状态枚举
# =============================================================================


class ApiKeyStatus(str, Enum):
    """API Key 状态"""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


# =============================================================================
# API Key 格式常量
# =============================================================================


class ApiKeyFormat:
    """API Key 格式常量"""

    PREFIX = "sk"  # Secret Key 前缀
    SEPARATOR = "_"  # 分隔符
    KEY_ID_LENGTH = 16  # key_id 长度（用于日志识别）
    SECRET_LENGTH = 32  # 随机密钥长度

    # 完整 Key 长度: sk_16chars_32chars
    FULL_KEY_LENGTH = (
        len(PREFIX) + len(SEPARATOR) + KEY_ID_LENGTH + len(SEPARATOR) + SECRET_LENGTH
    )  # 52

    @classmethod
    def get_prefix(cls) -> str:
        """获取完整前缀（包含分隔符）"""
        return f"{cls.PREFIX}{cls.SEPARATOR}"

    @classmethod
    def mask_key(cls, key: str) -> str:
        """掩码显示 Key（只显示前缀和后 4 位）"""
        if len(key) < 8:
            return "***"
        return f"{key[:7]}...{key[-4:]}"


# =============================================================================
# 领域实体
# =============================================================================


@dataclass(slots=True)
class ApiKeyGatewayGrantEntity:
    """平台 API Key 的 Gateway 团队授权策略。

    ``X-Team-Id`` 只允许选择这里已授权的团队；模型、能力与限流按 grant 生效。
    """

    id: uuid.UUID
    api_key_id: uuid.UUID
    user_id: uuid.UUID
    team_id: uuid.UUID
    allowed_models: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    rpm_limit: int | None
    tpm_limit: int | None
    store_full_messages: bool
    guardrail_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ApiKeyEntity:
    """API Key 领域实体

    封装 API Key 的业务逻辑和状态。
    """

    id: uuid.UUID
    user_id: uuid.UUID
    key_hash: str
    key_id: str
    key_prefix: str
    name: str
    description: str | None
    scopes: set[ApiKeyScope]
    expires_at: datetime
    is_active: bool
    last_used_at: datetime | None
    usage_count: int
    created_at: datetime
    updated_at: datetime
    gateway_grants: tuple[ApiKeyGatewayGrantEntity, ...] = ()

    # =======================================================================
    # 业务规则方法
    # =======================================================================

    @property
    def status(self) -> ApiKeyStatus:
        """获取当前状态"""
        if not self.is_active:
            return ApiKeyStatus.REVOKED
        if datetime.now(UTC) > self.expires_at:
            return ApiKeyStatus.EXPIRED
        return ApiKeyStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """是否有效（激活且未过期）"""
        return self.is_active and not self.is_expired

    @property
    def days_until_expiry(self) -> int:
        """距离过期天数"""
        delta = self.expires_at - datetime.now(UTC)
        return max(0, delta.days)

    def can_access(self, required_scope: ApiKeyScope) -> bool:
        """检查是否有指定作用域权限"""
        if not self.is_valid:
            return False
        return required_scope in self.scopes

    def can_access_any(self, required_scopes: set[ApiKeyScope]) -> bool:
        """检查是否有任一作用域权限"""
        if not self.is_valid:
            return False
        return bool(self.scopes & required_scopes)


# =============================================================================
# Request/Response DTO
# =============================================================================


class ApiKeyGatewayGrantRequest(BaseModel):
    """创建/更新平台 API Key 时配置 Gateway 团队授权。"""

    team_id: uuid.UUID
    allowed_models: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    rpm_limit: int | None = Field(default=None, ge=1)
    tpm_limit: int | None = Field(default=None, ge=1)
    store_full_messages: bool = False
    guardrail_enabled: bool = True

    @field_validator("allowed_models")
    @classmethod
    def normalize_allowed_models(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            model = str(item).strip()
            if model and model not in seen:
                seen.add(model)
                out.append(model)
        return out

    @field_validator("allowed_capabilities")
    @classmethod
    def normalize_allowed_capabilities(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            capability = str(item).strip()
            if not capability:
                continue
            if capability not in GATEWAY_PROXY_CAPABILITY_VALUES:
                raise ValueError(f"invalid gateway capability: {capability}")
            if capability not in seen:
                seen.add(capability)
                out.append(capability)
        return out


class ApiKeyCreateRequest(BaseModel):
    """创建 API Key 请求"""

    name: str = Field(..., min_length=1, max_length=100, description="Key 名称")
    description: str | None = Field(None, max_length=500, description="描述")
    scopes: list[ApiKeyScope] = Field(
        default_factory=lambda: list(API_KEY_SCOPE_GROUPS["read_only"]),
        description="权限范围",
    )
    expires_in_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="有效期（天），必须设置",
    )
    gateway_grants: list[ApiKeyGatewayGrantRequest] = Field(
        default_factory=list,
        description=(
            "gateway:proxy 的团队授权。为空时仅自动授予当前用户 personal team；"
            "调用时 X-Team-Id 只能选择已授权团队。"
        ),
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[ApiKeyScope]) -> set[ApiKeyScope]:
        """确保作用域不为空"""
        if not v:
            return API_KEY_SCOPE_GROUPS["read_only"]
        return set(v)


class ApiKeyUpdateRequest(BaseModel):
    """更新 API Key 请求"""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    scopes: list[ApiKeyScope] | None = None
    extend_expiry_days: int | None = Field(None, ge=1, le=365)
    gateway_grants: list[ApiKeyGatewayGrantRequest] | None = None


class ApiKeyGatewayGrantResponse(BaseModel):
    """平台 API Key 的 Gateway 团队授权响应。"""

    id: str
    team_id: str
    allowed_models: list[str]
    allowed_capabilities: list[str]
    rpm_limit: int | None
    tpm_limit: int | None
    store_full_messages: bool
    guardrail_enabled: bool
    is_active: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, entity: ApiKeyGatewayGrantEntity) -> ApiKeyGatewayGrantResponse:
        return cls(
            id=str(entity.id),
            team_id=str(entity.team_id),
            allowed_models=list(entity.allowed_models),
            allowed_capabilities=list(entity.allowed_capabilities),
            rpm_limit=entity.rpm_limit,
            tpm_limit=entity.tpm_limit,
            store_full_messages=entity.store_full_messages,
            guardrail_enabled=entity.guardrail_enabled,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )


class ApiKeyResponse(BaseModel):
    """API Key 响应"""

    id: str
    name: str
    description: str | None
    scopes: list[ApiKeyScope]
    expires_at: datetime
    is_active: bool
    status: ApiKeyStatus
    last_used_at: datetime | None
    usage_count: int
    created_at: datetime
    masked_key: str  # 掩码后的 Key，用于展示
    gateway_grants: list[ApiKeyGatewayGrantResponse] = Field(default_factory=list)

    @classmethod
    def from_entity(cls, entity: ApiKeyEntity) -> ApiKeyResponse:
        """从领域实体创建响应"""
        masked_key = f"{entity.key_prefix}{entity.key_id[:8]}***"
        return cls(
            id=str(entity.id),
            name=entity.name,
            description=entity.description,
            scopes=list(entity.scopes),
            expires_at=entity.expires_at,
            is_active=entity.is_active,
            status=entity.status,
            last_used_at=entity.last_used_at,
            usage_count=entity.usage_count,
            created_at=entity.created_at,
            masked_key=masked_key,
            gateway_grants=[
                ApiKeyGatewayGrantResponse.from_entity(g) for g in entity.gateway_grants
            ],
        )


class ApiKeyCreatedResponse(BaseModel):
    """API Key 创建响应（仅创建时返回完整 Key）"""

    api_key: ApiKeyResponse
    plain_key: str  # 完整 Key，仅此机会返回
    warning: str = "请妥善保存此 API Key，之后将无法再次查看完整值"


class ApiKeyUsageLogResponse(BaseModel):
    """API Key 使用日志响应"""

    id: str
    endpoint: str
    method: str
    ip_address: str | None
    user_agent: str | None
    status_code: int
    response_time_ms: int | None
    created_at: datetime
