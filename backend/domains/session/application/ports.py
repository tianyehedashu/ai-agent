"""
Session Application Ports - 会话应用端口

定义被它域（如 Agent）调用的会话应用能力抽象，符合 DDD/六边形架构。
实现类为 SessionUseCase，在组合根注入。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import uuid

    from domains.session.domain.entities import SessionOwner


@dataclass(frozen=True)
class TitleLlmChatResult:
    """标题生成 LLM 调用的最小结果（Session 域契约，不依赖 Agent DTO）。"""

    content: str | None = None


class TitleLlmPort(Protocol):
    """标题生成所需的 LLM 调用端口（由 Agent 域实现）。"""

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> TitleLlmChatResult:
        """返回可解析为标题文本的内容。"""
        ...


class SessionApplicationPort(Protocol):
    """会话应用端口

    Agent 域依赖此接口获取/创建会话、校验所有权、写消息等。
    SessionUseCase 为实现类，由组合根注入。
    """

    async def create_session(
        self,
        user_id: str,
        agent_id: str | None = None,
        title: str | None = None,
    ) -> Any:
        """创建会话"""
        ...

    async def get_session(self, session_id: str) -> Any:
        """获取会话"""
        ...

    async def get_session_with_ownership_check(
        self,
        session_id: str,
        owner: SessionOwner,
    ) -> Any:
        """获取会话并验证所有权"""
        ...

    async def get_or_create_session_for_principal(
        self,
        principal_id: str,
        session_id: str | None = None,
        *,
        title: str | None = None,
        agent_id: str | None = None,
    ) -> tuple[Any, bool]:
        """按 Principal 获取或创建会话（含所有权校验）。返回 (会话, 是否新建)。"""
        ...

    async def update_session(
        self,
        session_id: str,
        title: str | None = ...,
        status: str | None = ...,
        gateway_verbose_request_log: bool | None = ...,
        creative_mode: str | None = ...,
        image_gen_model_ref: str | None = ...,
        video_model_ref: str | None = ...,
    ) -> Any:
        """更新会话（如标题、状态、网关详细请求日志开关）。"""
        ...

    async def add_message(
        self,
        session_id: str,
        role: Any,
        content: str | None = None,
        tool_calls: dict | None = None,
        tool_call_id: str | None = None,
        metadata: dict | None = None,
        token_count: int | None = None,
    ) -> Any:
        """添加消息"""
        ...

    async def count_messages(self, session_id: str) -> int:
        """统计会话的消息数量"""
        ...

    async def count_total(self) -> int:
        """统计会话总数"""
        ...

    async def count_active_today(self) -> int:
        """统计今日活跃会话数"""
        ...

    async def count_by_user(self, user_id: str) -> int:
        """统计指定用户的会话数"""
        ...

    async def sum_tokens_by_user(self, user_id: str) -> int:
        """统计指定用户所有会话 token 总量"""
        ...

    async def list_session_ids_by_user(self, user_id: str) -> list[uuid.UUID]:
        """列出指定用户的会话 ID"""
        ...

    async def update_session_mcp_config(self, session_id: str, enabled_servers: list[str]) -> dict:
        """更新会话的 MCP 配置"""
        ...

    async def update_session_chat_model_ref(
        self, session_id: str, model_ref: str | None, *, flush: bool = True
    ) -> None:
        """合并写入会话 config.chat_model_ref（None 表示清除）。"""
        ...

    async def merge_session_config_fragment(
        self, session_id: str, fragment: dict[str, Any], *, flush: bool = True
    ) -> None:
        """浅合并写入会话 config 片段（如 creative_mode、image_gen_model_ref）。"""
        ...

    async def increment_video_task_count(self, session_id: str, count: int = 1) -> None:
        """增加会话的视频任务计数"""
        ...
