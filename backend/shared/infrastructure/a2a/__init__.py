"""
Agent-to-Agent (A2A) 调用模块

支持 Agent 之间的通信和协作
"""

from shared.infrastructure.a2a.client import A2AClient
from shared.infrastructure.a2a.registry import AgentRegistry

__all__ = [
    "A2AClient",
    "AgentRegistry",
]
