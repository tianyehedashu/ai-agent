"""
Title Use Case - 标题生成用例

编排标题生成相关的操作。
"""

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.runtime.application.session_use_case import SessionUseCase
from domains.runtime.domain.entities.session import SessionDomainService, SessionOwner
from domains.runtime.domain.services.title_rules import is_default_title
from shared.infrastructure.llm.gateway import LLMGateway
from shared.kernel.types import Principal
from utils.logging import get_logger

logger = get_logger(__name__)


class TitleUseCase:
    """标题生成用例

    提供灵活的标题生成策略，支持异步处理，不阻塞对话流程。
    """

    def __init__(self, db: AsyncSession, llm_gateway: LLMGateway | None = None):
        self.db = db
        self.session_use_case = SessionUseCase(db)
        self.llm_gateway = llm_gateway or LLMGateway(config=settings)
        self.domain_service = SessionDomainService()

    def _create_owner_from_user_id(self, user_id: str) -> SessionOwner:
        """从用户 ID 创建 SessionOwner"""
        is_anonymous = Principal.is_anonymous_id(user_id)
        return SessionOwner.from_principal_id(user_id, is_anonymous)

    @staticmethod
    def _normalize_llm_response(response: object) -> str:
        """将 LLM 返回结果规范化为字符串"""
        if isinstance(response, str):
            return response
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content
        return str(response)

    async def generate_from_first_message(self, message: str) -> str | None:
        """根据第一条消息生成标题"""
        try:
            message_preview = message[:200] if len(message) > 200 else message

            prompt = f"""根据以下用户消息，生成一个简洁的会话标题（不超过8个字）：

用户消息：{message_preview}

只返回标题，不要其他内容。标题应该简洁明了，能够概括对话主题。"""

            response = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model=settings.fast_model,
                max_tokens=20,
                temperature=0.7,
            )

            title = self._normalize_llm_response(response).strip().strip('"').strip("'").strip()
            title = title.rstrip(")").rstrip(".").rstrip(")").rstrip("!")
            if len(title) > 50:
                title = title[:47] + "..."

            return title if title else None
        except Exception as e:
            logger.warning("Failed to generate title from first message: %s", e, exc_info=True)
            return None

    async def generate_from_summary(self, session_id: str, max_messages: int = 10) -> str | None:
        """根据多条消息总结生成标题"""
        try:
            messages = await self.session_use_case.get_messages(
                session_id, skip=0, limit=max_messages
            )

            if not messages:
                return None

            message_summary = []
            for msg in messages:
                if msg.content:
                    role = "用户" if msg.role == "user" else "助手"
                    content_preview = msg.content[:100] if len(msg.content) > 100 else msg.content
                    message_summary.append(f"{role}: {content_preview}")

            conversation_text = "\n".join(message_summary)

            prompt = f"""根据以下对话内容，生成一个简洁的会话标题（不超过8个字）：

对话内容：
{conversation_text}

只返回标题，不要其他内容。标题应该简洁明了，能够概括整个对话的主题。"""

            response = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model=settings.fast_model,
                max_tokens=20,
                temperature=0.7,
            )

            title = self._normalize_llm_response(response).strip().strip('"').strip("'").strip()
            title = title.rstrip(")").rstrip(".").rstrip(")").rstrip("!")
            if len(title) > 50:
                title = title[:47] + "..."

            return title if title else None
        except Exception as e:
            logger.warning("Failed to generate title from summary: %s", e, exc_info=True)
            return None

    async def update_title(self, session_id: str, title: str, user_id: str) -> bool:
        """更新会话标题（手动修改）"""
        try:
            session = await self.session_use_case.get_session(session_id)
            if not session:
                logger.warning("Session not found: %s", session_id)
                return False

            owner = self._create_owner_from_user_id(user_id)
            if not self.domain_service.check_ownership(session, owner):
                logger.warning(
                    "User %s attempted to update session %s (not authorized)",
                    user_id[:20] if len(user_id) > 20 else user_id,
                    session_id,
                )
                return False

            if len(title) > 200:
                title = title[:197] + "..."

            await self.session_use_case.update_session(session_id, title=title)
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
        """生成并更新标题"""
        try:
            if not await self._validate_session_for_title_generation(session_id, user_id):
                return False

            title = await self._generate_title_by_strategy(strategy, session_id, message)
            if not title:
                return False

            await self.session_use_case.update_session(session_id, title=title)
            logger.info(
                "Generated and updated title (%s): %s for session %s",
                strategy,
                title,
                session_id[:8],
            )
            return True
        except Exception as e:
            logger.warning("Failed to generate and update title: %s", e, exc_info=True)
            return False

    async def _validate_session_for_title_generation(
        self, session_id: str, user_id: str | None
    ) -> bool:
        """验证会话是否可以进行标题生成"""
        session = await self.session_use_case.get_session(session_id)
        if not session:
            return False

        if user_id:
            owner = self._create_owner_from_user_id(user_id)
            if not self.domain_service.check_ownership(session, owner):
                return False

        if is_default_title(session.title):
            logger.debug(
                "Session %s has default title '%s', allowing auto-generation",
                session_id[:8],
                session.title or "(None)",
            )
            return True

        logger.debug(
            "Session %s already has custom title '%s', skipping auto-generation",
            session_id[:8],
            session.title[:20] if len(session.title) > 20 else session.title,
        )
        return False

    async def _generate_title_by_strategy(
        self,
        strategy: Literal["first_message", "summary"],
        session_id: str,
        message: str | None,
    ) -> str | None:
        """根据策略生成标题"""
        if strategy == "first_message" and message:
            return await self.generate_from_first_message(message)

        if strategy == "summary":
            return await self.generate_from_summary(session_id)

        logger.warning("Invalid strategy or missing message: %s", strategy)
        return None
