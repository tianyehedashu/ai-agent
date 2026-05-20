"""LLM adapter for session title generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.session.application.ports import TitleLlmChatResult, TitleLlmPort

if TYPE_CHECKING:
    from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade


class LlmTitleGenerationAdapter(TitleLlmPort):
    """将 AgentLlmFacade 适配为 Session 域 TitleLlmPort。"""

    def __init__(self, agent_llm_facade: AgentLlmFacade) -> None:
        self._llm = agent_llm_facade

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> TitleLlmChatResult:
        response = await self._llm.chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if isinstance(response, str):
            return TitleLlmChatResult(content=response)
        content = getattr(response, "content", None)
        return TitleLlmChatResult(content=content if isinstance(content, str) else None)


__all__ = ["LlmTitleGenerationAdapter"]
