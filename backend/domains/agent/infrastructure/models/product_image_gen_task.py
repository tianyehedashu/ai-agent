"""
Product Image Gen Task Model - 产品 8 图生成任务

一次生成 8 张图（第 1 张白底）的任务记录。
"""

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TenantScopedMixin


class ProductImageGenTaskStatus:
    """8 图生成任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductImageGenTask(BaseModel, TenantScopedMixin):
    """产品 8 图生成任务。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "product_image_gen_tasks"

    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="refs product_info_jobs.id (no DB FK)",
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
