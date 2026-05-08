"""
Product Info Job Step Model - 产品信息工作流步骤

单次原子能力执行记录，含输入快照与输出快照，供后续步骤复用。
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.orm.base import BaseModel

if TYPE_CHECKING:
    from domains.agent.infrastructure.models.product_info_job import ProductInfoJob


class ProductInfoJobStepStatus:
    """步骤状态"""

    PENDING = "pending"
    PROMPT_GENERATING = "prompt_generating"
    PROMPT_READY = "prompt_ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductInfoJobStep(BaseModel):
    """产品信息工作流步骤"""

    __tablename__ = "product_info_job_steps"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_info_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="步骤顺序 1,2,3...",
    )
    capability_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="image_analysis, product_link_analysis, competitor_link_analysis, video_script, image_gen_prompts",
    )
    input_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="本次执行时的完整输入（含注入的前步结果）",
    )
    output_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="本步执行结果，供后续步骤复用",
    )
    meta_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="用户编写的元提示词",
    )
    generated_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Phase 1 LLM 生成的详细提示词",
    )
    prompt_used: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Phase 2 实际使用的提示词（= generated_prompt 或用户编辑版）",
    )
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="若使用用户模板则存模板 id",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ProductInfoJobStepStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    job: Mapped["ProductInfoJob"] = relationship(
        "ProductInfoJob",
        back_populates="steps",
    )

    def __repr__(self) -> str:
        return f"<ProductInfoJobStep {self.id} {self.capability_id} {self.status}>"
