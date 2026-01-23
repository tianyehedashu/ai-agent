"""
Tree-of-Thought (ToT) 推理模式

思维树多路径探索模式，适用于创意生成、策略规划
"""

from domains.agent.domain.types import AgentState, Message
from domains.agent.infrastructure.reasoning.base import BaseReasoningMode, ReasoningResult


class TreeOfThoughtMode(BaseReasoningMode):
    """
    Tree-of-Thought 模式

    特点：
    - 探索多个思考路径
    - 评估不同方案的优劣
    - 选择最佳路径
    - 适合需要创意的任务
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.branch_count = self.config.get("branch_count", 3)
        self.max_depth = self.config.get("max_depth", 3)

    def get_system_prompt(self) -> str:
        return f"""你是一个智能助手，使用 Tree-of-Thought 模式解决问题。

工作方式：
1. 生成多个思考路径（至少{self.branch_count}个）
2. 评估每个路径的可行性
3. 选择最佳路径继续探索
4. 重复直到找到解决方案

输出格式：
探索路径：
路径1: [思路1] - 评估: [优点/缺点]
路径2: [思路2] - 评估: [优点/缺点]
路径3: [思路3] - 评估: [优点/缺点]

选择路径: [路径X]
继续探索: [深入分析]
"""

    async def reason(
        self,
        state: AgentState,
        context: list[Message],
        available_tools: list[str],
    ) -> ReasoningResult:
        """ToT 推理逻辑"""
        thought = f"探索多个思考路径，评估并选择最佳方案（生成{self.branch_count}个分支）。"

        return ReasoningResult(
            thought=thought,
            confidence=0.75,  # ToT 不确定性较高
        )
