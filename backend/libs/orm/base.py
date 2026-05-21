"""
Base Model - 模型基类

包含:
- TimestampMixin: 时间戳混入类
- TenantScopedMixin / AuditableMixin / PolicyTargetMixin: 多租户与审计
- BaseModel: 模型基类
"""

from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from libs.db.database import Base


def generate_uuid() -> uuid.UUID:
    """生成 UUID"""
    return uuid.uuid4()


# =============================================================================
# 多租户 / 审计 / 策略挂载（协议）
# =============================================================================


@runtime_checkable
class TenantScopedProtocol(Protocol):
    """多租户协议：业务表通过 tenant_id 归属团队（personal / shared）。"""

    tenant_id: uuid.UUID


class TenantScopedMixin:
    """多租户混入类。

    默认提供 ``tenant_id UUID NOT NULL + index``，**不设 DB 外键**
    （由应用层保证引用完整性；与项目主流约定一致）。

    若某张表确需 DB 外键或其他差异（罕见），在子类内同名 ``mapped_column``
    显式覆盖即可——会替换 ``declared_attr`` 生成的列。

    系统级配置请使用 ``system_*`` 表，勿在本表留 NULL tenant。
    """

    @declared_attr
    @classmethod
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            nullable=False,
            index=True,
        )


class AuditableMixin:
    """审计字段（不参与行级授权）。子类按需声明 ``created_by`` / ``updated_by`` 列。"""

    created_by: "Mapped[uuid.UUID | None]"
    updated_by: "Mapped[uuid.UUID | None]"


class PolicyTargetProtocol(Protocol):
    """策略挂载协议（与 tenant 正交）。"""

    target_kind: str | None
    target_id: uuid.UUID | None


class PolicyTargetMixin:
    """策略挂载混入类（EntitlementPlan、按 vkey 的 Budget 等）。

    各子类的 ``target_kind`` / ``target_id`` nullable / index 约束差异较大，
    Mixin 仅作类型协议，列在子类显式声明。
    """

    target_kind: "Mapped[str | None]"
    target_id: "Mapped[uuid.UUID | None]"


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
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),  # Python 层面自动填充
        server_default=func.now(),  # pylint: disable=not-callable
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
