"""
Plan-Act 推理模式

先规划后执行模式，适用于多步骤任务
"""

from domains.agent.domain.types import AgentState, Message
from domains.agent.infrastructure.reasoning.base import BaseReasoningMode, ReasoningResult


class PlanActMode(BaseReasoningMode):
    """
    Plan-Act 模式

    特点：
    - 先制定完整计划
    - 然后按计划逐步执行
    - 适合多步骤、可预测的任务
    """

    def get_system_prompt(self) -> str:
        return """你是一个智能助手，使用 Plan-Act 模式解决问题。

工作流程：
1. Plan: 分析任务，制定详细的执行计划
2. Execute: 按照计划逐步执行
3. Review: 检查执行结果，必要时调整计划

输出格式：
Plan:
1. [步骤1]
2. [步骤2]
3. [步骤3]

Executing Step 1: [执行步骤1]
Result: [结果]

Executing Step 2: [执行步骤2]
Result: [结果]

...
"""

    async def reason(
        self,
        state: AgentState,
        context: list[Message],
        available_tools: list[str],
    ) -> ReasoningResult:
        """Plan-Act 推理逻辑"""
        thought = "分析任务，制定详细的执行计划。"

        # 如果有历史消息，尝试提取已有的计划
        plan = None
        for msg in reversed(context):
            if msg.role == "assistant" and "Plan:" in (msg.content or ""):
                # 提取计划步骤
                plan = self._extract_plan(msg.content or "")
                break

        return ReasoningResult(
            thought=thought,
            plan=plan or [],
            confidence=0.9,
        )

    def _extract_plan(self, content: str) -> list[str]:
        """从消息中提取计划步骤"""
        steps = []
        lines = content.split("\n")
        in_plan = False

        for line in lines:
            if "Plan:" in line:
                in_plan = True
                continue
            if in_plan and line.strip().startswith(("1.", "2.", "3.", "-")):
                step = line.strip().lstrip("1234567890.- ").strip()
                if step:
                    steps.append(step)
            elif in_plan and not line.strip():
                continue
            elif in_plan:
                break

        return steps
