"""
Reflect 推理模式

执行后反思改进模式，适用于高质量输出要求
"""

from domains.runtime.infrastructure.reasoning.base import BaseReasoningMode, ReasoningResult
from shared.types import AgentState, Message


class ReflectMode(BaseReasoningMode):
    """
    Reflect 模式

    特点：
    - 先执行任务
    - 然后反思结果
    - 识别问题并改进
    - 适合需要高质量输出的任务
    """

    def get_system_prompt(self) -> str:
        return """你是一个智能助手，使用 Reflect 模式解决问题。

工作流程：
1. Execute: 执行任务，生成初始结果
2. Reflect: 反思结果，识别问题
3. Improve: 改进结果
4. 重复步骤2-3，直到满意

输出格式：
Initial Result: [初始结果]

Reflection:
- 问题1: [发现的问题]
- 问题2: [发现的问题]

Improved Result: [改进后的结果]

Final Reflection: [最终评估]
"""

    async def reason(
        self,
        state: AgentState,
        context: list[Message],
        available_tools: list[str],
    ) -> ReasoningResult:
        """Reflect 推理逻辑"""
        # 检查是否有初始结果需要反思
        has_initial_result = any(
            msg.role == "assistant" and "Initial Result:" in (msg.content or "") for msg in context
        )

        if has_initial_result:
            thought = "反思当前结果，识别问题并提出改进方案。"
        else:
            thought = "执行任务，生成初始结果。"

        return ReasoningResult(
            thought=thought,
            confidence=0.9,
        )
