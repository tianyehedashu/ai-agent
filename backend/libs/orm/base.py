"""
Base Model - 模型基类

包含:
- TimestampMixin: 时间戳混入类
- OwnedMixin: 所有权混入类
- BaseModel: 模型基类
"""

from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.database import Base


def generate_uuid() -> uuid.UUID:
    """生成 UUID"""
    return uuid.uuid4()


# =============================================================================
# 所有权协议和混入类
# =============================================================================


@runtime_checkable
class OwnedProtocol(Protocol):
    """所有权协议 - 用于类型检查

    定义拥有所有权的模型必须实现的接口。
    """

    user_id: uuid.UUID | None
    anonymous_user_id: str | None


class OwnedMixin:
    """所有权混入类

    为模型提供所有权字段的类型声明和通用方法。
    各模型仍然自己定义字段（必填/可选），Mixin 只提供类型协议。

    使用方式：
    - Agent: 继承 OwnedMixin，user_id 必填
    - Session: 继承 OwnedMixin，user_id 可选，anonymous_user_id 可选

    Example:
        class Agent(BaseModel, OwnedMixin):
            user_id: Mapped[uuid.UUID] = mapped_column(...)  # 必填

        class Session(BaseModel, OwnedMixin):
            user_id: Mapped[uuid.UUID | None] = mapped_column(...)  # 可选
            anonymous_user_id: Mapped[str | None] = mapped_column(...)  # 可选
    """

    # 类型声明（不定义字段，由子类自己定义）
    # 使用字符串注解避免循环导入
    user_id: "Mapped[uuid.UUID | None]"
    anonymous_user_id: "Mapped[str | None] | None"

    def is_owned_by(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
    ) -> bool:
        """检查是否被指定用户拥有

        Args:
            user_id: 注册用户 ID
            anonymous_user_id: 匿名用户 ID

        Returns:
            是否被指定用户拥有
        """
        # 优先检查匿名用户
        if anonymous_user_id and hasattr(self, "anonymous_user_id"):
            return getattr(self, "anonymous_user_id", None) == anonymous_user_id
        # 检查注册用户
        if user_id:
            return getattr(self, "user_id", None) == user_id
        return False


# =============================================================================
# 时间戳混入类
# =============================================================================


class TimestampMixin:
    """时间戳混入类

    使用 Python 层面的 default 和数据库层面的 server_default 双重保障：
    - default: 在 Python 对象创建时自动填充，确保即使数据库没有默认值也能工作
    - server_default: 在数据库层面也有默认值，作为后备，并且对于直接 SQL 插入也有用
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),  # Python 层面自动填充
        server_default=func.now(),  # 数据库层面默认值（作为后备
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),  # Python 层面自动填充
        server_default=func.now(),  # 数据库层面默认值（作为后备
        onupdate=lambda: datetime.now(UTC),  # Python 层面自动更新
        nullable=False,
    )


class BaseModel(Base, TimestampMixin):
    """模型基类"""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
