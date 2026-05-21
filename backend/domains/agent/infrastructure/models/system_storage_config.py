"""System Storage Config ORM - 平台对象存储 singleton 配置。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.orm.base import BaseModel

if TYPE_CHECKING:
    from domains.identity.infrastructure.models.user import User


class SystemStorageConfig(BaseModel):
    """平台级对象存储配置（单行 singleton）。"""

    __tablename__ = "system_storage_config"

    storage_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="local",
        comment="存储类型: local | s3",
    )
    local_storage_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="本地存储目录",
    )
    local_serve_prefix: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        server_default="/api/v1/listing-studio/images",
        comment="本地模式 URL 前缀",
    )
    s3_bucket: Mapped[str | None] = mapped_column(String(200), nullable=True)
    s3_region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    s3_endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_access_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    s3_secret_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_public_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_upload_max_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="10485760",
        comment="上传大小上限（字节）",
    )
    public_access: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="refs users.id (no DB FK)",
    )

    if TYPE_CHECKING:
        updated_by_user: Mapped[User | None]


__all__ = ["SystemStorageConfig"]
