"""LLM adapter for session title generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.session.application.ports import TitleLlmPort

if TYPE_CHECKING:
    from domains.agent.infrastructure.llm.gateway import LLMGateway


class LlmTitleGenerationAdapter(TitleLlmPort):
    """将 LLMGateway 适配为 Session 域 TitleLlmPort。"""

    def __init__(self, llm_gateway: LLMGateway) -> None:
        self._llm = llm_gateway

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> object:
        return await self._llm.chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )


__all__ = ["LlmTitleGenerationAdapter"]
