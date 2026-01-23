"""
推理模式模块 (Reasoning Modes)

支持多种推理策略：
- ReAct: 推理↔行动交替
- Plan-Act: 先规划后执行
- CoT: 思维链逐步推导
- ToT: 思维树多路径探索
- Reflect: 执行后反思改进
"""

from domains.agent.infrastructure.reasoning.base import BaseReasoningMode, ReasoningResult
from domains.agent.infrastructure.reasoning.cot import ChainOfThoughtMode
from domains.agent.infrastructure.reasoning.plan_act import PlanActMode
from domains.agent.infrastructure.reasoning.react import ReActMode
from domains.agent.infrastructure.reasoning.reflect import ReflectMode
from domains.agent.infrastructure.reasoning.tot import TreeOfThoughtMode

__all__ = [
    "BaseReasoningMode",
    "ChainOfThoughtMode",
    "PlanActMode",
    "ReActMode",
    "ReasoningResult",
    "ReflectMode",
    "TreeOfThoughtMode",
]
