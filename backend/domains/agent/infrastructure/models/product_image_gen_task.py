"""
Product Image Gen Task Model - 产品 8 图生成任务

一次生成 8 张图（第 1 张白底）的任务记录。
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, OwnedMixin


class ProductImageGenTaskStatus:
    """8 图生成任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductImageGenTask(BaseModel, OwnedMixin):
    """产品 8 图生成任务"""

    __tablename__ = "product_image_gen_tasks"

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
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_info_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的产品信息任务",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ProductImageGenTaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    prompts: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="'[]'::jsonb",
        comment="8 条 { slot, prompt, model?, size? }",
    )
    result_images: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="8 条 { slot, url }",
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ProductImageGenTask {self.id} status={self.status}>"
