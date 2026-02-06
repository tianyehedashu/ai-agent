"""
Video Gen Task Model - 视频生成任务模型

存储视频生成任务的状态、提示词和结果。
"""

from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.orm.base import BaseModel, OwnedMixin

if TYPE_CHECKING:
    from domains.identity.infrastructure.models.user import User
    from domains.session.infrastructure.models.session import Session


class VideoGenTaskStatus:
    """视频生成任务状态"""

    PENDING = "pending"  # 待提交
    RUNNING = "running"  # 已提交，等待生成
    COMPLETED = "completed"  # 生成完成
    FAILED = "failed"  # 生成失败
    CANCELLED = "cancelled"  # 已取消


class VideoGenTask(BaseModel, OwnedMixin):
    """视频生成任务模型

    继承 OwnedMixin 提供所有权相关的类型协议和方法。
    支持注册用户（user_id）和匿名用户（anonymous_user_id）。
    """

    __tablename__ = "video_gen_tasks"

    # 所有权字段
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
        comment="匿名用户ID，用于未登录用户的任务",
    )

    # 关联会话（可选）
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的会话ID",
    )

    # 厂商任务标识
    workflow_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="厂商返回的 workflow_id",
    )
    run_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="厂商返回的 run_id",
    )

    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20),
        default=VideoGenTaskStatus.PENDING,
        nullable=False,
        index=True,
        comment="任务状态: pending, running, completed, failed, cancelled",
    )

    # 提示词相关
    prompt_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="完整的视频生成提示词",
    )
    prompt_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="提示词来源: agent_generated, user_provided, template",
    )

    # 视频生成配置
    model: Mapped[str] = mapped_column(
        String(50),
        default="openai::sora1.0",
        nullable=False,
        comment="视频生成模型: openai::sora1.0, openai::sora2.0",
    )
    duration: Mapped[int] = mapped_column(
        default=5,
        nullable=False,
        comment="视频时长（秒）: sora1支持5/10/15/20, sora2支持5/10/15",
    )

    # 参考图片与站点
    reference_images: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="'[]'::jsonb",
        comment="参考图片 URL 列表",
    )
    marketplace: Mapped[str] = mapped_column(
        String(10),
        default="jp",
        nullable=False,
        comment="目标站点: jp, us, de, uk, fr, it, es 等",
    )

    # 结果
    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="厂商返回的完整结果（含 video_url 等）",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )

    # 关系
    user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    session: Mapped["Session | None"] = relationship(
        "Session",
        back_populates="video_tasks",
    )

    def __repr__(self) -> str:
        return f"<VideoGenTask {self.id} status={self.status}>"

    @property
    def video_url(self) -> str | None:
        """从 result 中提取视频 URL，支持厂商 API 的多种数据结构。

        支持的路径（按优先级）：
        - result.result.video_handle.generate_videos[0].video_url
        - result.video_handle.generate_videos[0].video_url
        - result.generate_videos[0].video_url
        - result.video_url
        - result.result.video_url
        """
        if not self.result:
            return None

        # 尝试多种路径（与 VideoAPIClient.extract_video_url 保持一致）
        paths_to_try = [
            # 标准路径: result.result.video_handle.generate_videos[0].video_url
            lambda r: r.get("result", {})
            .get("video_handle", {})
            .get("generate_videos", [{}])[0]
            .get("video_url"),
            # 无 result 包装: result.video_handle.generate_videos[0].video_url
            lambda r: r.get("video_handle", {}).get("generate_videos", [{}])[0].get("video_url"),
            # 直接 generate_videos: result.generate_videos[0].video_url
            lambda r: r.get("generate_videos", [{}])[0].get("video_url"),
            # 直接 video_url: result.video_url
            lambda r: r.get("video_url"),
            # result.result.video_url
            lambda r: r.get("result", {}).get("video_url"),
        ]

        for path_fn in paths_to_try:
            try:
                url = path_fn(self.result)
                if url and isinstance(url, str) and url.startswith("http"):
                    return url
            except (AttributeError, IndexError, KeyError, TypeError):
                continue

        return None
