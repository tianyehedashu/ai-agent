"""
Base Model - 模型基类
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.db.database import Base


def generate_uuid() -> uuid.UUID:
    """生成 UUID"""
    return uuid.uuid4()


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
