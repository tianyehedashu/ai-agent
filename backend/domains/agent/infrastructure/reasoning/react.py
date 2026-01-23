"""
ReAct 推理模式

推理↔行动交替模式，适用于需要工具的复杂任务
"""

from domains.agent.domain.types import AgentState, Message
from domains.agent.infrastructure.reasoning.base import BaseReasoningMode, ReasoningResult


class ReActMode(BaseReasoningMode):
    """
    ReAct (Reasoning + Acting) 模式

    特点：
    - 推理和行动交替进行
    - 每次行动后观察结果，再继续推理
    - 适合需要多步工具调用的任务
    """

    def get_system_prompt(self) -> str:
        return """你是一个智能助手，使用 ReAct 模式解决问题。

工作流程：
1. Thought: 分析当前情况，思考下一步行动
2. Action: 调用合适的工具
3. Observation: 观察工具返回的结果
4. 重复步骤1-3，直到问题解决

输出格式：
Thought: [你的思考]
Action: [工具名称](参数)
Observation: [工具返回结果]
Thought: [继续思考]
...
Final Answer: [最终答案]
"""

    async def reason(
        self,
        state: AgentState,
        context: list[Message],
        available_tools: list[str],
    ) -> ReasoningResult:
        """
        ReAct 推理逻辑

        在 ReAct 模式下，推理和行动是交替进行的。
        实际的推理由 LLM 完成，这里主要提供格式指导。
        """
        # ReAct 模式的核心是让 LLM 按照 Thought -> Action -> Observation 循环
        # 实际的推理在 LLM 响应中完成，这里返回格式化的思考
        # 可以根据上下文调整思考内容
        thought = "分析当前情况，确定下一步需要执行的操作。"

        return ReasoningResult(
            thought=thought,
            confidence=0.8,
        )
