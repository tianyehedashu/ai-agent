"""
Title Service - 会话标题生成服务

提供多种标题生成策略：
- 根据第一条消息生成
- 根据多条消息总结生成
- 支持手动修改
"""

from enum import Enum
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from core.llm.gateway import LLMGateway
from app.config import settings
from services.session import SessionService
from utils.logging import get_logger

logger = get_logger(__name__)


class TitleGenerationStrategy(str, Enum):
    """标题生成策略"""

    FIRST_MESSAGE = "first_message"  # 根据第一条消息生成
    SUMMARY = "summary"  # 根据多条消息总结生成
    MANUAL = "manual"  # 手动设置


class TitleService:
    """标题生成服务

    提供灵活的标题生成策略，支持异步处理，不阻塞对话流程。
    """

    def __init__(self, db: AsyncSession, llm_gateway: LLMGateway | None = None):
        self.db = db
        self.session_service = SessionService(db)
        self.llm_gateway = llm_gateway or LLMGateway(config=settings)

    async def generate_from_first_message(self, message: str) -> str | None:
        """根据第一条消息生成标题

        Args:
            message: 用户的第一条消息

        Returns:
            生成的标题，如果生成失败则返回 None
        """
        try:
            # 限制消息长度，避免提示词过长
            message_preview = message[:200] if len(message) > 200 else message

            prompt = f"""根据以下用户消息，生成一个简洁的会话标题（3-8个字）：

用户消息：{message_preview}

只返回标题，不要其他内容。标题应该简洁明了，能够概括对话主题。"""

            response = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo",  # 使用小模型降低成本
                max_tokens=20,
                temperature=0.7,
            )

            # 清理响应：移除引号、换行等
            title = response.strip().strip('"').strip("'").strip()
            # 移除可能的标点符号
            title = title.rstrip("。").rstrip(".").rstrip("！").rstrip("!")
            # 限制标题长度（数据库字段限制为200，但UI显示建议50以内）
            if len(title) > 50:
                title = title[:47] + "..."

            return title if title else None
        except Exception as e:
            logger.warning("Failed to generate title from first message: %s", e, exc_info=True)
            return None

    async def generate_from_summary(
        self, session_id: str, max_messages: int = 10
    ) -> str | None:
        """根据多条消息总结生成标题

        Args:
            session_id: 会话 ID
            max_messages: 最多使用的消息数量

        Returns:
            生成的标题，如果生成失败则返回 None
        """
        try:
            # 获取会话消息
            messages = await self.session_service.get_messages(
                session_id, skip=0, limit=max_messages
            )

            if not messages:
                return None

            # 构建消息摘要
            message_summary = []
            for msg in messages:
                if msg.content:
                    role = "用户" if msg.role == "user" else "助手"
                    content_preview = (
                        msg.content[:100] if len(msg.content) > 100 else msg.content
                    )
                    message_summary.append(f"{role}: {content_preview}")

            conversation_text = "\n".join(message_summary)

            prompt = f"""根据以下对话内容，生成一个简洁的会话标题（3-8个字）：

对话内容：
{conversation_text}

只返回标题，不要其他内容。标题应该简洁明了，能够概括整个对话的主题。"""

            response = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo",  # 使用小模型降低成本
                max_tokens=20,
                temperature=0.7,
            )

            # 清理响应
            title = response.strip().strip('"').strip("'").strip()
            title = title.rstrip("。").rstrip(".").rstrip("！").rstrip("!")
            if len(title) > 50:
                title = title[:47] + "..."

            return title if title else None
        except Exception as e:
            logger.warning("Failed to generate title from summary: %s", e, exc_info=True)
            return None

    async def update_title(
        self, session_id: str, title: str, user_id: str
    ) -> bool:
        """更新会话标题（手动修改）

        Args:
            session_id: 会话 ID
            title: 新标题
            user_id: 用户 ID（用于权限检查）

        Returns:
            是否更新成功
        """
        try:
            # 验证会话存在且属于当前用户
            session = await self.session_service.get_by_id(session_id)
            if not session:
                logger.warning("Session not found: %s", session_id)
                return False

            if str(session.user_id) != user_id:
                logger.warning(
                    "User %s attempted to update session %s owned by %s",
                    user_id,
                    session_id,
                    session.user_id,
                )
                return False

            # 限制标题长度
            if len(title) > 200:
                title = title[:197] + "..."

            await self.session_service.update(session_id, title=title)
            logger.info("Updated session title: %s for session %s", title, session_id[:8])
            return True
        except Exception as e:
            logger.error("Failed to update session title: %s", e, exc_info=True)
            return False

    async def generate_and_update(
        self,
        session_id: str,
        strategy: Literal["first_message", "summary"],
        message: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """生成并更新标题

        Args:
            session_id: 会话 ID
            strategy: 生成策略
            message: 第一条消息（strategy="first_message" 时使用）
            user_id: 用户 ID（用于权限检查）

        Returns:
            是否更新成功
        """
        try:
            # 检查会话是否存在且有权限
            session = await self.session_service.get_by_id(session_id)
            if not session:
                return False

            if user_id and str(session.user_id) != user_id:
                return False

            # 如果已有标题，不自动生成（避免覆盖手动设置的标题）
            if session.title:
                logger.debug("Session %s already has title, skipping auto-generation", session_id[:8])
                return False

            # 根据策略生成标题
            if strategy == "first_message" and message:
                title = await self.generate_from_first_message(message)
            elif strategy == "summary":
                title = await self.generate_from_summary(session_id)
            else:
                logger.warning("Invalid strategy or missing message: %s", strategy)
                return False

            if title:
                await self.session_service.update(session_id, title=title)
                logger.info(
                    "Generated and updated title (%s): %s for session %s",
                    strategy,
                    title,
                    session_id[:8],
                )
                return True

            return False
        except Exception as e:
            logger.warning("Failed to generate and update title: %s", e, exc_info=True)
            return False
