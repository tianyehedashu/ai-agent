"""
Product Info Job Model - 产品信息工作流实例

一次完整的产品信息管道（图片分析 → 商品/竞品分析 → 视频脚本 → 8图提示词）的容器。
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.orm.base import BaseModel, OwnedMixin

if TYPE_CHECKING:
    from domains.agent.infrastructure.models.product_info_job_step import ProductInfoJobStep
    from domains.identity.infrastructure.models.user import User
    from domains.session.infrastructure.models.session import Session


class ProductInfoJobStatus:
    """产品信息任务状态"""

    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分步骤失败


class ProductInfoJob(BaseModel, OwnedMixin):
    """产品信息工作流实例"""

    __tablename__ = "product_info_jobs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    anonymous_user_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="匿名用户ID",
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联会话ID",
    )
    title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="任务标题",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ProductInfoJobStatus.DRAFT,
        nullable=False,
        index=True,
        comment="draft, running, completed, failed, partial",
    )

    steps: Mapped[list["ProductInfoJobStep"]] = relationship(
        "ProductInfoJobStep",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ProductInfoJobStep.sort_order",
    )
    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id])
    session: Mapped["Session | None"] = relationship(
        "Session",
        foreign_keys=[session_id],
    )

    def __repr__(self) -> str:
        return f"<ProductInfoJob {self.id} status={self.status}>"
