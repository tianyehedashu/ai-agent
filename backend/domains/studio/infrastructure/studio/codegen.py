"""
LangGraph Code Generator - 代码生成器

从可视化定义生成 LangGraph Python 代码
"""

from typing import Any

from domains.studio.infrastructure.studio.parser import (
    EdgeDefinition,
    NodeDefinition,
    WorkflowDefinition,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class LangGraphCodeGen:
    """
    LangGraph 代码生成器

    从工作流定义生成 Python 代码
    """

    def __init__(self) -> None:
        self.indent = "    "

    def generate(self, workflow: WorkflowDefinition) -> str:
        """
        生成代码

        Args:
            workflow: 工作流定义

        Returns:
            生成的 Python 代码
        """
        lines: list[str] = []

        # 导入语句
        lines.extend(self._generate_imports(workflow))
        lines.append("")

        # 状态类
        if workflow.state_class:
            lines.extend(self._generate_state_class(workflow))
            lines.append("")

        # 节点函数占位
        lines.extend(self._generate_node_functions(workflow))
        lines.append("")

        # 条件函数占位
        lines.extend(self._generate_condition_functions(workflow))
        lines.append("")

        # 图定义
        lines.extend(self._generate_graph(workflow))

        return "\n".join(lines)

    def _generate_imports(self, workflow: WorkflowDefinition) -> list[str]:
        """生成导入语句"""
        imports = [
            "from typing import TypedDict, Annotated, Sequence",
            "from langgraph.graph import StateGraph, END",
        ]

        # 根据节点类型添加导入
        node_types = {n.node_type for n in workflow.nodes}
        if "llm" in node_types:
            imports.append("from langchain_openai import ChatOpenAI")

        return imports

    def _generate_state_class(self, workflow: WorkflowDefinition) -> list[str]:
        """生成状态类"""
        class_name = workflow.state_class or "AgentState"
        return [
            f"class {class_name}(TypedDict):",
            f'{self.indent}"""Agent 状态"""',
            f"{self.indent}messages: Sequence[dict]",
            f"{self.indent}next_action: str",
        ]

    def _generate_node_functions(self, workflow: WorkflowDefinition) -> list[str]:
        """生成节点函数"""
        lines = ["# ========== 节点函数 =========="]

        for node in workflow.nodes:
            lines.extend(
                [
                    "",
                    f"def {node.function_name}(state: {workflow.state_class or 'AgentState'}):",
                    f'{self.indent}"""节点: {node.name}"""',
                    f"{self.indent}# TODO: 实现节点逻辑",
                    f"{self.indent}return state",
                ]
            )

        return lines

    def _generate_condition_functions(self, workflow: WorkflowDefinition) -> list[str]:
        """生成条件函数"""
        if not workflow.conditional_edges:
            return []

        lines = ["# ========== 条件函数 =========="]

        for cond in workflow.conditional_edges:
            if not cond.condition_func:
                continue

            paths = list(cond.path_map.keys())
            lines.extend(
                [
                    "",
                    (
                        f"def {cond.condition_func}"
                        f"(state: {workflow.state_class or 'AgentState'}) -> str:"
                    ),
                    f'{self.indent}"""条件路由"""',
                    f"{self.indent}# TODO: 实现路由逻辑",
                    f'{self.indent}return "{paths[0] if paths else "default"}"',
                ]
            )

        return lines

    def _generate_graph(self, workflow: WorkflowDefinition) -> list[str]:
        """生成图定义"""
        state_class = workflow.state_class or "AgentState"
        lines = [
            "# ========== 图定义 ==========",
            "",
            f"graph = StateGraph({state_class})",
            "",
            "# 添加节点",
        ]

        # 添加节点
        for node in workflow.nodes:
            lines.append(f'graph.add_node("{node.id}", {node.function_name})')

        lines.append("")
        lines.append("# 添加边")

        # 分离普通边和条件边
        normal_edges = [e for e in workflow.edges if e.edge_type == "default"]
        cond_edge_sources = {c.source for c in workflow.conditional_edges}

        for edge in normal_edges:
            # 跳过已有条件边的源节点
            if edge.source in cond_edge_sources:
                continue

            target = "END" if edge.target == "__end__" else f'"{edge.target}"'
            lines.append(f'graph.add_edge("{edge.source}", {target})')

        # 条件边
        for cond in workflow.conditional_edges:
            lines.append("")
            lines.append("graph.add_conditional_edges(")
            lines.append(f'{self.indent}"{cond.source}",')
            lines.append(f"{self.indent}{cond.condition_func},")
            lines.append(f"{self.indent}{{")
            for value, target in cond.path_map.items():
                target_str = "END" if target == "__end__" else f'"{target}"'
                lines.append(f'{self.indent}{self.indent}"{value}": {target_str},')
            lines.append(f"{self.indent}}}")
            lines.append(")")

        # 入口点
        if workflow.entry_point:
            lines.append("")
            lines.append(f'graph.set_entry_point("{workflow.entry_point}")')

        # 编译
        lines.extend(
            [
                "",
                "# 编译图",
                "app = graph.compile()",
            ]
        )

        return lines

    def add_node(
        self,
        code: str,
        node: NodeDefinition,
    ) -> str:
        """
        向现有代码添加节点

        Args:
            code: 现有代码
            node: 节点定义

        Returns:
            修改后的代码
        """
        # 找到 add_node 调用的位置
        lines = code.split("\n")
        insert_idx = -1

        for i, line in enumerate(lines):
            if "graph.add_node" in line:
                insert_idx = i + 1

        if insert_idx == -1:
            # 找 StateGraph 定义
            for i, line in enumerate(lines):
                if "StateGraph" in line:
                    insert_idx = i + 2
                    break

        if insert_idx == -1:
            insert_idx = len(lines)

        # 生成新的 add_node 调用
        new_line = f'graph.add_node("{node.id}", {node.function_name})'
        lines.insert(insert_idx, new_line)

        # 添加函数定义 (如果不存在)
        if node.function_name not in code:
            func_lines = [
                "",
                f"def {node.function_name}(state):",
                f'{self.indent}"""节点: {node.name}"""',
                f"{self.indent}return state",
                "",
            ]
            # 找到合适的插入位置
            for i, line in enumerate(lines):
                if "# ========== 节点函数" in line or "def " in line:
                    lines = lines[:i] + func_lines + lines[i:]
                    break
            else:
                lines = func_lines + lines

        return "\n".join(lines)

    def add_edge(
        self,
        code: str,
        edge: EdgeDefinition,
    ) -> str:
        """
        向现有代码添加边

        Args:
            code: 现有代码
            edge: 边定义

        Returns:
            修改后的代码
        """
        lines = code.split("\n")
        insert_idx = -1

        for i, line in enumerate(lines):
            if "graph.add_edge" in line:
                insert_idx = i + 1

        if insert_idx == -1:
            for i, line in enumerate(lines):
                if "graph.add_node" in line:
                    insert_idx = i + 1

        if insert_idx == -1:
            insert_idx = len(lines) - 1

        target = "END" if edge.target == "__end__" else f'"{edge.target}"'
        new_line = f'graph.add_edge("{edge.source}", {target})'
        lines.insert(insert_idx, new_line)

        return "\n".join(lines)

    def remove_node(self, code: str, node_id: str) -> str:
        """
        从代码中移除节点

        Args:
            code: 现有代码
            node_id: 节点 ID

        Returns:
            修改后的代码
        """
        lines = code.split("\n")
        new_lines = []

        for line in lines:
            # 跳过该节点的 add_node 调用
            if f'graph.add_node("{node_id}"' in line:
                continue
            # 跳过相关的边
            if f'"{node_id}"' in line and ("add_edge" in line or "add_conditional_edges" in line):
                continue
            new_lines.append(line)

        return "\n".join(new_lines)

    def from_react_flow(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        state_class: str = "AgentState",
    ) -> str:
        """
        从 React Flow 格式生成代码

        Args:
            nodes: React Flow 节点
            edges: React Flow 边
            state_class: 状态类名

        Returns:
            生成的代码
        """
        # 转换节点
        node_defs = []
        for node in nodes:
            data = node.get("data", {})
            node_defs.append(
                NodeDefinition(
                    id=node["id"],
                    name=data.get("label", node["id"]),
                    node_type=data.get("nodeType", "custom"),
                    function_name=data.get("function", f"node_{node['id']}"),
                    position=(
                        int(node.get("position", {}).get("x", 0)),
                        int(node.get("position", {}).get("y", 0)),
                    ),
                )
            )

        # 转换边
        edge_defs = []
        for edge in edges:
            edge_defs.append(
                EdgeDefinition(
                    source=edge["source"],
                    target=edge["target"],
                    edge_type="conditional" if edge.get("animated") else "default",
                    condition=edge.get("label"),
                )
            )

        # 找入口点 (没有入边的节点)
        targets = {e.target for e in edge_defs}
        {e.source for e in edge_defs}
        entry_points = [n.id for n in node_defs if n.id not in targets]
        entry_point = entry_points[0] if entry_points else (node_defs[0].id if node_defs else None)

        # 构建工作流定义
        workflow = WorkflowDefinition(
            name="workflow",
            state_class=state_class,
            nodes=node_defs,
            edges=edge_defs,
            conditional_edges=[],
            entry_point=entry_point,
            finish_point=None,
        )

        return self.generate(workflow)
