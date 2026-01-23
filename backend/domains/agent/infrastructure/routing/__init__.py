"""
条件路由模块 (Conditional Routing)

实现确定性路由逻辑，不依赖 LLM 判断，流程可预测
"""

from domains.agent.infrastructure.routing.router import RouteDecision, StateRouter

__all__ = [
    "RouteDecision",
    "StateRouter",
]
