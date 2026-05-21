"""
Listing Studio Prompt Template Model - Listing 提示词模板（用户）

按能力维度存储用户保存的提示词模板；系统默认提示词不落库。
"""

import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel, TenantScopedMixin


class ListingStudioPromptTemplate(BaseModel, TenantScopedMixin):
    """Listing Studio 提示词模板（用户自定义）。

    ``tenant_id`` 由 ``TenantScopedMixin`` 提供（无 DB FK）。
    """

    __tablename__ = "product_info_prompt_templates"

    capability_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="image_analysis, product_link_analysis, ...",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="模板名称",
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="文本提示词（前 4 个能力用）",
    )
    prompts: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="8 条提示词数组，仅 image_gen_prompts 用",
    )

    def __repr__(self) -> str:
        return f"<ListingStudioPromptTemplate {self.id} {self.capability_id} {self.name}>"
