"""
Chain-of-Thought (CoT) 推理模式

思维链逐步推导模式，适用于数学计算、逻辑分析
"""

from domains.agent.domain.types import AgentState, Message
from domains.agent.infrastructure.reasoning.base import BaseReasoningMode, ReasoningResult


class ChainOfThoughtMode(BaseReasoningMode):
    """
    Chain-of-Thought 模式

    特点：
    - 逐步推导，展示思考过程
    - 适合需要逻辑推理的问题
    - 不涉及工具调用，纯推理
    """

    def get_system_prompt(self) -> str:
        return """你是一个智能助手，使用 Chain-of-Thought 模式解决问题。

工作方式：
- 逐步展示你的思考过程
- 每一步都要有清晰的逻辑
- 最后给出结论

输出格式：
思考过程：
1. [第一步分析]
2. [第二步分析]
3. [第三步分析]

结论：[最终答案]
"""

    async def reason(
        self,
        state: AgentState,
        context: list[Message],
        available_tools: list[str],
    ) -> ReasoningResult:
        """CoT 推理逻辑"""
        thought = "逐步分析问题，展示完整的思考过程。"

        return ReasoningResult(
            thought=thought,
            confidence=0.85,
        )
