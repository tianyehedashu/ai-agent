"""
API Key Models - API Key 模型

包含:
- ApiKey: API Key 主表
- ApiKeyUsageLog: 使用日志表

设计决策：
- 不使用数据库外键约束（性能考虑，应用层保证完整性）
- 不定义 ORM relationship（避免无外键时的关系推断问题）
- 业务逻辑在 Domain Entity (ApiKeyEntity) 中，ORM Model 仅负责数据存储
"""

from datetime import UTC, datetime
import uuid

from sqlalchemy import ARRAY, Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TimestampMixin


class ApiKey(BaseModel, TimestampMixin):
    """API Key 模型

    存储用户的 API Key 信息，用于自动化脚本访问。
    完整 Key 以哈希形式存储，明文仅在创建时返回。

    注意：业务逻辑（如 status、is_valid 等）在 Domain Entity 中实现。
    """

    __tablename__ = "api_keys"

    # 用户关联
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="所属用户 ID",
    )

    # Key 信息
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="哈希后的 API Key",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="sk_",
        comment="Key 前缀，如 'sk_'",
    )
    key_id: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
        comment="随机标识符（16字符），用于日志识别",
    )

    # 元数据
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="用户自定义名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="描述",
    )
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="权限范围数组",
    )

    # 过期策略（强制设置）
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="过期时间（必填）",
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="是否激活",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后使用时间",
    )

    # 审计
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="使用次数",
    )

    # 加密后的完整密钥（用于用户查看）
    encrypted_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="加密后的完整密钥",
    )

    def __repr__(self) -> str:
        return f"<ApiKey {self.masked_key_display}>"

    @property
    def masked_key_display(self) -> str:
        """掩码显示 Key（用于 UI 展示）

        格式: sk_1234...mnop
        """
        return f"{self.key_prefix}{self.key_id[:4]}...***"

    @property
    def _status_for_query(self) -> str:
        """状态字符串（用于数据库查询，业务逻辑在 Domain Entity）

        Returns:
            'active' | 'expired' | 'revoked'
        """
        if not self.is_active:
            return "revoked"
        if datetime.now(UTC) > self.expires_at:
            return "expired"
        return "active"


class ApiKeyUsageLog(BaseModel):
    """API Key 使用日志模型

    记录每次 API Key 调用的详细信息，用于审计。
    """

    __tablename__ = "api_key_usage_logs"

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联的 API Key ID",
    )

    # 请求信息
    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="请求端点",
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="HTTP 方法",
    )

    # 客户端信息
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # 支持 IPv6
        nullable=True,
        comment="客户端 IP",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User-Agent",
    )

    # 响应信息
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="HTTP 状态码",
    )
    response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="响应时间（毫秒）",
    )

    def __repr__(self) -> str:
        return f"<ApiKeyUsageLog {self.method} {self.endpoint}>"


class ApiKeyGatewayGrant(BaseModel, TimestampMixin):
    """平台 API Key 的 Gateway 团队授权。

    ``api_keys.scopes`` 只说明这把 Key 具备 Gateway 代理能力；本表才是它能访问
    哪些团队、模型和调用能力的授权真源。
    """

    __tablename__ = "api_key_gateway_grants"

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联的 API Key ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="API Key 所属用户 ID，用于授权校验和审计",
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="允许代理调用归属的 Gateway Team ID",
    )
    allowed_models: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)),
        default=list,
        nullable=False,
        comment="允许模型白名单；空数组表示不限制",
    )
    allowed_capabilities: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)),
        default=list,
        nullable=False,
        comment="允许 Gateway 能力；空数组表示不限制",
    )
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    store_full_messages: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否允许该平台 Key 的 Gateway 调用保存完整消息",
    )
    guardrail_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否启用 Gateway Guardrail",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="授权是否有效",
    )

    __table_args__ = (
        UniqueConstraint("api_key_id", "team_id", name="uq_api_key_gateway_grants_key_team"),
        Index("ix_api_key_gateway_grants_user_team", "user_id", "team_id"),
    )

    def __repr__(self) -> str:
        return f"<ApiKeyGatewayGrant api_key={self.api_key_id} team={self.team_id}>"
