"""
Studio Domain Types - 工作室域类型定义

包含工作流相关的类型：
- WorkflowDefinition: 工作流定义
- NodeDefinition: 节点定义
- EdgeDefinition: 边定义
"""

from typing import TypedDict

# ============================================================================
# TypedDict (字典类型约束)
# ============================================================================


class NodeDefinition(TypedDict):
    """节点定义 (用于 Code-First 解析)"""

    id: str
    name: str
    func_name: str
    position: tuple[int, int]


class EdgeDefinition(TypedDict):
    """边定义"""

    source: str
    target: str
    condition: str | None


class WorkflowDefinition(TypedDict):
    """工作流定义"""

    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    entry_point: str
