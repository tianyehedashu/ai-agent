"""
LangGraph Parser - 代码解析器

解析 Python 代码，提取 LangGraph 工作流定义:
- add_node 调用
- add_edge 调用
- conditional_edges 调用
- StateGraph 状态类
"""

import ast
from dataclasses import dataclass, field
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class NodeDefinition:
    """节点定义"""

    id: str
    name: str
    node_type: str  # llm, tool, condition, custom
    function_name: str
    position: tuple[int, int] = (0, 0)
    config: dict[str, Any] = field(default_factory=dict)
    line_number: int = 0


@dataclass
class EdgeDefinition:
    """边定义"""

    source: str
    target: str
    edge_type: str = "default"  # default, conditional
    condition: str | None = None
    line_number: int = 0


@dataclass
class ConditionalEdge:
    """条件边定义"""

    source: str
    condition_func: str
    path_map: dict[str, str]
    line_number: int = 0


@dataclass
class WorkflowDefinition:
    """工作流定义"""

    name: str
    state_class: str | None
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    conditional_edges: list[ConditionalEdge]
    entry_point: str | None
    finish_point: str | None


class LangGraphParser:
    """
    LangGraph 代码解析器

    从 Python 代码中提取工作流结构
    """

    def __init__(self) -> None:
        self.nodes: list[NodeDefinition] = []
        self.edges: list[EdgeDefinition] = []
        self.conditional_edges: list[ConditionalEdge] = []
        self.state_class: str | None = None
        self.entry_point: str | None = None
        self.finish_point: str | None = None
        self.graph_var: str | None = None

    def parse(self, code: str) -> WorkflowDefinition:
        """
        解析代码

        Args:
            code: Python 代码

        Returns:
            WorkflowDefinition: 工作流定义
        """
        self.nodes = []
        self.edges = []
        self.conditional_edges = []
        self.state_class = None
        self.entry_point = None
        self.finish_point = None
        self.graph_var = None

        try:
            tree = ast.parse(code)
            self._visit(tree)
        except SyntaxError as e:
            logger.error("Syntax error in code: %s", e)
            raise ValueError(f"Invalid Python syntax: {e}") from e

        # 计算节点位置
        self._calculate_positions()

        return WorkflowDefinition(
            name="workflow",
            state_class=self.state_class,
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
            entry_point=self.entry_point,
            finish_point=self.finish_point,
        )

    def _visit(self, node: ast.AST) -> None:
        """访问 AST 节点"""
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                self._handle_assign(child)
            elif isinstance(child, ast.Call):
                self._handle_call(child)
            elif isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                self._handle_call(child.value, child.lineno)

    def _handle_assign(self, node: ast.Assign) -> None:
        """处理赋值语句"""
        # 检测 StateGraph 创建
        if isinstance(node.value, ast.Call) and self._is_state_graph_call(node.value):
            # 提取图变量名
            if node.targets and isinstance(node.targets[0], ast.Name):
                self.graph_var = node.targets[0].id

            # 提取状态类
            if node.value.args:
                arg = node.value.args[0]
                if isinstance(arg, ast.Name):
                    self.state_class = arg.id

    def _handle_call(self, node: ast.Call, line_no: int = 0) -> None:
        """处理函数调用"""
        line_no = line_no or getattr(node, "lineno", 0)

        # 检测方法调用 (graph.add_node, graph.add_edge 等)
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr

            if method_name == "add_node":
                self._parse_add_node(node, line_no)
            elif method_name == "add_edge":
                self._parse_add_edge(node, line_no)
            elif method_name == "add_conditional_edges":
                self._parse_conditional_edges(node, line_no)
            elif method_name == "set_entry_point":
                self._parse_entry_point(node)
            elif method_name == "set_finish_point":
                self._parse_finish_point(node)

    def _is_state_graph_call(self, node: ast.Call) -> bool:
        """检查是否是 StateGraph 调用"""
        if isinstance(node.func, ast.Name):
            return node.func.id == "StateGraph"
        if isinstance(node.func, ast.Attribute):
            return node.func.attr == "StateGraph"
        return False

    def _parse_add_node(self, node: ast.Call, line_no: int) -> None:
        """解析 add_node 调用"""
        if len(node.args) < 2:
            return

        # 节点名称
        node_name = self._get_string_value(node.args[0])
        if not node_name:
            return

        # 节点函数
        func_name = ""
        if isinstance(node.args[1], ast.Name):
            func_name = node.args[1].id
        elif isinstance(node.args[1], ast.Attribute):
            func_name = node.args[1].attr

        # 推断节点类型
        node_type = self._infer_node_type(func_name)

        self.nodes.append(
            NodeDefinition(
                id=node_name,
                name=node_name,
                node_type=node_type,
                function_name=func_name,
                line_number=line_no,
            )
        )

    def _parse_add_edge(self, node: ast.Call, line_no: int) -> None:
        """解析 add_edge 调用"""
        if len(node.args) < 2:
            return

        source = self._get_string_value(node.args[0])
        target = self._get_string_value(node.args[1])

        if source and target:
            self.edges.append(
                EdgeDefinition(
                    source=source,
                    target=target,
                    edge_type="default",
                    line_number=line_no,
                )
            )

    def _parse_conditional_edges(self, node: ast.Call, line_no: int) -> None:
        """解析 add_conditional_edges 调用"""
        if len(node.args) < 2:
            return

        source = self._get_string_value(node.args[0])

        # 条件函数
        condition_func = ""
        if isinstance(node.args[1], ast.Name):
            condition_func = node.args[1].id

        # 路径映射
        path_map: dict[str, str] = {}
        if len(node.args) >= 3 and isinstance(node.args[2], ast.Dict):
            for key, value in zip(node.args[2].keys, node.args[2].values, strict=False):
                k = self._get_string_value(key) if key else None
                v = self._get_string_value(value)
                if k and v:
                    path_map[k] = v

        if source:
            self.conditional_edges.append(
                ConditionalEdge(
                    source=source,
                    condition_func=condition_func,
                    path_map=path_map,
                    line_number=line_no,
                )
            )

            # 为每个路径创建边
            for condition_value, target in path_map.items():
                self.edges.append(
                    EdgeDefinition(
                        source=source,
                        target=target,
                        edge_type="conditional",
                        condition=condition_value,
                        line_number=line_no,
                    )
                )

    def _parse_entry_point(self, node: ast.Call) -> None:
        """解析入口点"""
        if node.args:
            self.entry_point = self._get_string_value(node.args[0])

    def _parse_finish_point(self, node: ast.Call) -> None:
        """解析结束点"""
        if node.args:
            self.finish_point = self._get_string_value(node.args[0])

    def _get_string_value(self, node: ast.AST | None) -> str | None:
        """获取字符串值"""
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Str):  # Python 3.7 兼容
            return node.s
        if isinstance(node, ast.Name):
            # 检查是否是 END 常量
            if node.id == "END":
                return "__end__"
            return node.id
        return None

    def _infer_node_type(self, func_name: str) -> str:
        """推断节点类型"""
        func_lower = func_name.lower()

        if "llm" in func_lower or "chat" in func_lower or "model" in func_lower:
            return "llm"
        if "tool" in func_lower or "execute" in func_lower:
            return "tool"
        if "condition" in func_lower or "route" in func_lower or "should" in func_lower:
            return "condition"

        return "custom"

    def _calculate_positions(self) -> None:
        """计算节点位置 (简单的层次布局)"""
        if not self.nodes:
            return

        # 构建邻接表
        adjacency: dict[str, list[str]] = {n.id: [] for n in self.nodes}
        in_degree: dict[str, int] = {n.id: 0 for n in self.nodes}

        for edge in self.edges:
            if edge.source in adjacency and edge.target in adjacency:
                adjacency[edge.source].append(edge.target)
                in_degree[edge.target] += 1

        # 拓扑排序确定层级
        levels: dict[str, int] = {}
        queue = [n for n in in_degree if in_degree[n] == 0]

        # 如果有入口点，从入口点开始
        if self.entry_point and self.entry_point in in_degree:
            queue = [self.entry_point]

        level = 0
        while queue:
            next_queue = []
            for node_id in queue:
                if node_id not in levels:
                    levels[node_id] = level
                for target in adjacency.get(node_id, []):
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        next_queue.append(target)
            queue = next_queue
            level += 1

        # 分配位置
        level_counts: dict[int, int] = {}
        for node in self.nodes:
            node_level = levels.get(node.id, 0)
            count = level_counts.get(node_level, 0)
            level_counts[node_level] = count + 1

            # 水平间距 250，垂直间距 150
            node.position = (node_level * 250 + 50, count * 150 + 50)

    def to_react_flow(self, workflow: WorkflowDefinition) -> dict[str, Any]:
        """
        转换为 React Flow 格式

        Args:
            workflow: 工作流定义

        Returns:
            React Flow 节点和边
        """
        nodes = []
        edges = []

        # 节点类型到样式的映射
        type_styles = {
            "llm": {"background": "#e0f2fe", "border": "#0ea5e9"},
            "tool": {"background": "#fef3c7", "border": "#f59e0b"},
            "condition": {"background": "#f3e8ff", "border": "#a855f7"},
            "custom": {"background": "#f1f5f9", "border": "#64748b"},
        }

        for node in workflow.nodes:
            style = type_styles.get(node.node_type, type_styles["custom"])
            nodes.append(
                {
                    "id": node.id,
                    "type": node.node_type,
                    "position": {"x": node.position[0], "y": node.position[1]},
                    "data": {
                        "label": node.name,
                        "function": node.function_name,
                        "nodeType": node.node_type,
                    },
                    "style": {
                        "background": style["background"],
                        "border": f"2px solid {style['border']}",
                        "borderRadius": "8px",
                        "padding": "10px",
                    },
                }
            )

        for i, edge in enumerate(workflow.edges):
            edges.append(
                {
                    "id": f"e{i}",
                    "source": edge.source,
                    "target": edge.target,
                    "type": "smoothstep",
                    "animated": edge.edge_type == "conditional",
                    "label": edge.condition or "",
                    "style": {
                        "stroke": "#94a3b8" if edge.edge_type == "default" else "#a855f7",
                    },
                }
            )

        return {"nodes": nodes, "edges": edges}
