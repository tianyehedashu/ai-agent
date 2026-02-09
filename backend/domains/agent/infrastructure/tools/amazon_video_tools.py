"""
Amazon Video Tools - 亚马逊视频生成工具

提供视频生成任务的提交和轮询工具。
"""

import contextlib
import json
from typing import Any, ClassVar
import uuid

from pydantic import Field

from domains.agent.domain.types import ToolCategory, ToolResult
from domains.agent.infrastructure.tools.base import BaseTool, ToolParameters, register_tool
from domains.identity.domain.types import ANONYMOUS_ID_PREFIX
from libs.db.database import get_session_factory
from libs.db.permission_context import get_permission_context
from utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# 工具参数定义
# =============================================================================


class AmazonVideoSubmitParams(ToolParameters):
    """视频提交参数"""

    prompt: str = Field(description="完整的视频生成提示词，包含镜头、过渡、技术要求等")
    reference_images: list[str] = Field(default_factory=list, description="参考图片 URL 列表")
    marketplace: str = Field(
        default="jp",
        description="目标站点: jp(日语), us(英语), de(德语), uk(英语), fr(法语), it(意大利语), es(西班牙语)",
    )
    session_id: str | None = Field(default=None, description="关联的会话 ID（可选）")


class AmazonVideoPollParams(ToolParameters):
    """视频轮询参数"""

    task_id: str = Field(description="视频任务 ID")
    once: bool = Field(default=True, description="是否单次查询（不等待完成）")


class AmazonProductResearchParams(ToolParameters):
    """产品调研参数"""

    product_link: str | None = Field(default=None, description="产品链接（1688、供应商链接等）")
    extra_description: str | None = Field(
        default=None, description="用户提供的产品卖点、风格、场景说明"
    )
    reference_images: list[str] = Field(default_factory=list, description="参考图片 URL 列表")


class AmazonCompetitorResearchParams(ToolParameters):
    """竞品调研参数"""

    competitor_link: str | None = Field(default=None, description="竞品链接（亚马逊 listing 等）")
    competitor_description: str | None = Field(
        default=None, description="竞品描述或用户提供的竞品信息"
    )


# =============================================================================
# 视频提交工具
# =============================================================================


@register_tool
class AmazonVideoSubmitTool(BaseTool):
    """亚马逊视频提交工具

    提交视频生成任务到厂商 API，返回任务 ID 和状态。
    """

    name: ClassVar[str] = "amazon_video_submit"
    description: ClassVar[str] = (
        "提交亚马逊产品视频生成任务。需要提供完整的视频生成提示词（包含镜头、过渡等），"
        "可选提供参考图片和目标站点。返回任务 ID 用于后续轮询。"
    )
    category: ClassVar[ToolCategory] = ToolCategory.EXTERNAL
    requires_confirmation: ClassVar[bool] = True
    parameters_model: ClassVar[type[ToolParameters]] = AmazonVideoSubmitParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行视频提交"""
        params = AmazonVideoSubmitParams(**kwargs)

        try:
            ctx = get_permission_context()
            if ctx is None:
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error="无法获取用户权限上下文",
                )

            principal_id = (
                str(ctx.user_id) if ctx.user_id else f"{ANONYMOUS_ID_PREFIX}{ctx.anonymous_user_id}"
            )
            session_factory = get_session_factory()
            async with session_factory() as db:
                # 延迟导入避免循环依赖：engine -> tools -> amazon_video_tools -> application -> chat_use_case -> engine
                from domains.agent.application.video_task_use_case import (
                    VideoTaskUseCase,  # pylint: disable=import-outside-toplevel
                )
                from domains.session.application import (
                    SessionUseCase,  # pylint: disable=import-outside-toplevel
                )

                use_case = VideoTaskUseCase(db, session_use_case=SessionUseCase(db))

                # 解析 session_id
                session_uuid = None
                if params.session_id:
                    with contextlib.suppress(ValueError):
                        session_uuid = uuid.UUID(params.session_id)

                # 创建任务并自动提交
                task = await use_case.create_task(
                    principal_id=principal_id,
                    session_id=session_uuid,
                    prompt_text=params.prompt,
                    prompt_source="agent_generated",
                    reference_images=params.reference_images,
                    marketplace=params.marketplace,
                    auto_submit=True,
                )

            # 构建返回结果
            result_data = {
                "task_id": task["id"],
                "workflow_id": task.get("workflow_id"),
                "run_id": task.get("run_id"),
                "status": task["status"],
                "message": "视频生成任务已提交",
            }

            return ToolResult(
                tool_call_id="",
                success=True,
                output=json.dumps(result_data, ensure_ascii=False, indent=2),
            )

        except Exception as e:
            logger.error("Video submit failed: %s", e, exc_info=True)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"视频提交失败: {e}",
            )


# =============================================================================
# 视频轮询工具
# =============================================================================


@register_tool
class AmazonVideoPollTool(BaseTool):
    """亚马逊视频轮询工具

    查询视频生成任务的状态，返回当前状态和结果（如果已完成）。
    """

    name: ClassVar[str] = "amazon_video_poll"
    description: ClassVar[str] = (
        "查询亚马逊产品视频生成任务的状态。需要提供任务 ID，"
        "返回当前状态。如果任务已完成，返回视频 URL。"
    )
    category: ClassVar[ToolCategory] = ToolCategory.EXTERNAL
    requires_confirmation: ClassVar[bool] = False
    parameters_model: ClassVar[type[ToolParameters]] = AmazonVideoPollParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行视频轮询"""
        params = AmazonVideoPollParams(**kwargs)

        try:
            session_factory = get_session_factory()
            async with session_factory() as db:
                from domains.agent.application.video_task_use_case import (
                    VideoTaskUseCase,  # pylint: disable=import-outside-toplevel
                )
                from domains.session.application import (
                    SessionUseCase,  # pylint: disable=import-outside-toplevel
                )

                use_case = VideoTaskUseCase(db, session_use_case=SessionUseCase(db))

                # 轮询任务
                task = await use_case.poll_task(
                    task_id=uuid.UUID(params.task_id),
                    once=params.once,
                )

            # 构建返回结果
            result_data = {
                "task_id": task["id"],
                "status": task["status"],
                "workflow_id": task.get("workflow_id"),
                "run_id": task.get("run_id"),
            }

            if task["status"] == "completed":
                result_data["video_url"] = task.get("video_url")
                result_data["message"] = "视频生成已完成"
            elif task["status"] == "failed":
                result_data["error"] = task.get("error_message")
                result_data["message"] = "视频生成失败"
            else:
                result_data["message"] = "视频正在生成中"

            return ToolResult(
                tool_call_id="",
                success=True,
                output=json.dumps(result_data, ensure_ascii=False, indent=2),
            )

        except Exception as e:
            logger.error("Video poll failed: %s", e, exc_info=True)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"视频轮询失败: {e}",
            )


# =============================================================================
# 产品调研工具
# =============================================================================


@register_tool
class AmazonProductResearchTool(BaseTool):
    """亚马逊产品调研工具

    根据产品链接或描述生成产品调研摘要，包括品类、卖点、使用场景、目标人群等。
    """

    name: ClassVar[str] = "amazon_product_research"
    description: ClassVar[str] = (
        "根据产品链接或描述生成产品调研摘要。"
        "输出包括：品类分析、核心卖点、使用场景、目标人群等信息，"
        "用于后续的视频分镜设计。"
    )
    category: ClassVar[ToolCategory] = ToolCategory.EXTERNAL
    requires_confirmation: ClassVar[bool] = False
    parameters_model: ClassVar[type[ToolParameters]] = AmazonProductResearchParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行产品调研"""
        params = AmazonProductResearchParams(**kwargs)

        try:
            # 构建调研提示
            research_context = []
            if params.product_link:
                research_context.append(f"产品链接: {params.product_link}")
            if params.extra_description:
                research_context.append(f"产品描述: {params.extra_description}")
            if params.reference_images:
                research_context.append(f"参考图片: {', '.join(params.reference_images)}")

            if not research_context:
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error="请至少提供产品链接、描述或参考图片之一",
                )

            # 返回结构化调研指引，由 Agent 使用 web_fetch 等工具完成调研并生成报告
            result_data = {
                "status": "需要 Agent 进行调研",
                "input": "\n".join(research_context),
                "instructions": (
                    "请根据以上信息分析并生成产品调研报告，包括：\n"
                    "1. 产品品类和定位\n"
                    "2. 核心卖点（3-5个）\n"
                    "3. 主要使用场景\n"
                    "4. 目标人群画像\n"
                    "5. 差异化优势\n"
                    "如果提供了产品链接，可以使用 web_fetch 工具获取更多信息。"
                ),
            }

            return ToolResult(
                tool_call_id="",
                success=True,
                output=json.dumps(result_data, ensure_ascii=False, indent=2),
            )

        except Exception as e:
            logger.error("Product research failed: %s", e, exc_info=True)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"产品调研失败: {e}",
            )


# =============================================================================
# 竞品调研工具
# =============================================================================


@register_tool
class AmazonCompetitorResearchTool(BaseTool):
    """亚马逊竞品调研工具

    根据竞品链接或描述生成竞品分析摘要，包括优缺点、差异化点等。
    """

    name: ClassVar[str] = "amazon_competitor_research"
    description: ClassVar[str] = (
        "根据竞品链接或描述生成竞品分析摘要。"
        "输出包括：竞品优缺点、与我方产品的差异化点等信息，"
        "用于后续的视频分镜设计中的卖点强调。"
    )
    category: ClassVar[ToolCategory] = ToolCategory.EXTERNAL
    requires_confirmation: ClassVar[bool] = False
    parameters_model: ClassVar[type[ToolParameters]] = AmazonCompetitorResearchParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行竞品调研"""
        params = AmazonCompetitorResearchParams(**kwargs)

        try:
            # 构建调研提示
            research_context = []
            if params.competitor_link:
                research_context.append(f"竞品链接: {params.competitor_link}")
            if params.competitor_description:
                research_context.append(f"竞品描述: {params.competitor_description}")

            if not research_context:
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error="请至少提供竞品链接或竞品描述之一",
                )

            # 返回结构化竞品调研指引，由 Agent 使用 web_fetch 等工具完成调研并生成报告
            result_data = {
                "status": "需要 Agent 进行调研",
                "input": "\n".join(research_context),
                "instructions": (
                    "请根据以上信息分析并生成竞品调研报告，包括：\n"
                    "1. 竞品基本信息（名称、品牌、价格区间）\n"
                    "2. 竞品主要卖点\n"
                    "3. 竞品优势\n"
                    "4. 竞品劣势或不足\n"
                    "5. 与我方产品的差异化点\n"
                    "如果提供了竞品链接，可以使用 web_fetch 工具获取更多信息。"
                ),
            }

            return ToolResult(
                tool_call_id="",
                success=True,
                output=json.dumps(result_data, ensure_ascii=False, indent=2),
            )

        except Exception as e:
            logger.error("Competitor research failed: %s", e, exc_info=True)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"竞品调研失败: {e}",
            )
