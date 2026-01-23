"""
Types - 通用工具类型

仅包含与业务无关的通用泛型工具类型。

业务类型已下沉到对应域：
- Principal, ANONYMOUS_* → domains.identity.domain.types
- Message, AgentEvent, EventType, ... → domains.runtime.domain.types
"""

from libs.types.types import Result, T

__all__ = [
    "Result",
    "T",
]
