"""
Listing Studio Job Model - Listing 工作流实例

一次完整的 Listing 管道（图片分析 → 商品/竞品分析 → 视频脚本 → 8图提示词）的容器。
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.orm.base import BaseModel, TenantScopedMixin

if TYPE_CHECKING:
    from domains.agent.infrastructure.models.listing_studio_job_step import ListingStudioJobStep
    from domains.identity.infrastructure.models.user import User
    from domains.session.infrastructure.models.session import Session


from domains.agent.domain.listing_studio.types import ListingStudioJobStatus


class ListingStudioJob(BaseModel, TenantScopedMixin):
    """Listing Studio 工作流实例。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "product_info_jobs"

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="refs sessions.id (no DB FK)",
    )
    title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="任务标题",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ListingStudioJobStatus.DRAFT,
        nullable=False,
        index=True,
        comment="draft, running, completed, failed, partial",
    )

    steps: Mapped[list["ListingStudioJobStep"]] = relationship(
        "ListingStudioJobStep",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ListingStudioJobStep.sort_order",
        primaryjoin="ListingStudioJobStep.job_id == ListingStudioJob.id",
        foreign_keys="ListingStudioJobStep.job_id",
    )
    session: Mapped["Session | None"] = relationship(
        "Session",
        primaryjoin="ListingStudioJob.session_id == Session.id",
        foreign_keys="ListingStudioJob.session_id",
    )

    def __repr__(self) -> str:
        return f"<ListingStudioJob {self.id} status={self.status}>"
