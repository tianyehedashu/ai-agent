"""
Quota Models - 用户配额模型

包含:
- UserQuota: 用户配额配置（使用系统 Key 时的限制）
- QuotaUsageLog: 配额使用日志

设计决策：
- 配额按能力类型分别限制（文本、图像、Embedding）
- 支持每日和每月两种周期
- 用量日志记录详细的调用信息，用于审计和统计
"""

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TimestampMixin


class UserQuota(BaseModel, TimestampMixin):
    """用户配额配置

    存储用户使用系统 Key 时的配额限制。
    用户使用自己配置的 Key 时不受此配额限制。

    配额类型：
    - 每日文本请求数
    - 每日图像生成数
    - 每日 Embedding 请求数
    - 每月 Token 上限
    """

    __tablename__ = "user_quotas"

    # 用户关联
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        comment="所属用户 ID（一对一）",
    )

    # 每日配额限制
    daily_text_requests: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="每日文本请求数上限（None 表示无限制）",
    )
    daily_image_requests: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="每日图像生成数上限",
    )
    daily_embedding_requests: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="每日 Embedding 请求数上限",
    )

    # 每月配额限制
    monthly_token_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="每月 Token 上限",
    )

    # 当前周期已用量
    current_daily_text: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="当前每日文本请求已用量",
    )
    current_daily_image: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="当前每日图像生成已用量",
    )
    current_daily_embedding: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="当前每日 Embedding 已用量",
    )
    current_monthly_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="当前每月 Token 已用量",
    )

    # 配额重置时间
    daily_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="每日配额下次重置时间",
    )
    monthly_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="每月配额下次重置时间",
    )

    def needs_daily_reset(self) -> bool:
        """判断每日配额是否需要重置

        Returns:
            True 如果需要重置（重置时间已过期）
        """
        if self.daily_reset_at is None:
            return False
        return datetime.now(UTC) >= self.daily_reset_at

    def needs_monthly_reset(self) -> bool:
        """判断每月配额是否需要重置

        Returns:
            True 如果需要重置（重置时间已过期）
        """
        if self.monthly_reset_at is None:
            return False
        return datetime.now(UTC) >= self.monthly_reset_at

    def __repr__(self) -> str:
        return f"<UserQuota user={self.user_id}>"


class QuotaUsageLog(BaseModel):
    """配额使用日志

    记录每次 LLM 调用的详细信息，用于审计和统计。
    无论使用用户 Key 还是系统 Key 都会记录。
    """

    __tablename__ = "quota_usage_logs"

    # 用户关联
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="用户 ID",
    )

    # 调用信息
    capability: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="能力类型: text, image, embedding",
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="提供商: openai, anthropic, dashscope, etc.",
    )
    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="模型名称",
    )
    key_source: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Key 来源: user 或 system",
    )

    # 用量统计
    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="输入 Token 数",
    )
    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="输出 Token 数",
    )
    image_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="生成图像数",
    )
    cost_estimate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="估算费用（美元）",
    )

    # 时间戳（只需 created_at，不需要 updated_at）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<QuotaUsageLog {self.capability} {self.provider}>"
