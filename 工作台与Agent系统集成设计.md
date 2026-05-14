# 🔗 工作台与 Agent 系统集成设计

> **状态（2026-05）**：本文所述「工作台」与 Agent Core 的集成方案为**历史设计**；`domains/studio` 与 `/api/v1/studio/*` 等已从本仓库移除，正文中的路径与接口**不再代表现行实现**。

> 详细说明 Agent Studio（工作台）如何与 Agent Core（核心引擎）无缝集成

---

## 一、集成架构总览

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              完整系统架构                                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗ │
│  ║                          Agent Studio (工作台)                                 ║ │
│  ╠═══════════════════════════════════════════════════════════════════════════════╣ │
│  ║                                                                               ║ │
│  ║   ┌───────────────────────────────────────────────────────────────────────┐  ║ │
│  ║   │                         工作台前端 (React + Vite)                      │  ║ │
│  ║   │   [对话创建] [可视化编排] [提示词编辑] [调试测试] [部署管理]          │  ║ │
│  ║   └───────────────────────────────────────────────────────────────────────┘  ║ │
│  ║                                      │ API                                    ║ │
│  ║                                      ▼                                        ║ │
│  ║   ┌───────────────────────────────────────────────────────────────────────┐  ║ │
│  ║   │                    工作台服务层 (Studio Service)                       │  ║ │
│  ║   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  ║ │
│  ║   │   │ 对话创建器  │  │  编排引擎   │  │ 测试运行器  │  │ 部署管理器  │ │  ║ │
│  ║   │   │  Creator    │  │Orchestrator │  │ TestRunner  │  │  Deployer   │ │  ║ │
│  ║   │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │  ║ │
│  ║   └───────────────────────────────────────────────────────────────────────┘  ║ │
│  ║                                      │                                        ║ │
│  ╚══════════════════════════════════════╪════════════════════════════════════════╝ │
│                                         │                                          │
│                    ┌────────────────────┼────────────────────┐                     │
│                    │  配置转换          │  执行调用          │  数据同步           │
│                    ▼                    ▼                    ▼                     │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗ │
│  ║                           Agent Core (核心引擎)                                ║ │
│  ╠═══════════════════════════════════════════════════════════════════════════════╣ │
│  ║                                                                               ║ │
│  ║   ┌─────────────────────────────────────────────────────────────────────┐    ║ │
│  ║   │                     上下文管理器 (Context Manager)                   │    ║ │
│  ║   │      System Prompt │ 对话历史 │ 记忆召回 │ 工具结果 │ 任务状态       │    ║ │
│  ║   └─────────────────────────────────────────────────────────────────────┘    ║ │
│  ║                                      │                                        ║ │
│  ║   ┌─────────────────────────────────────────────────────────────────────┐    ║ │
│  ║   │                      执行循环 (Main Loop)                            │    ║ │
│  ║   │              输入 → 思考 → 决策 → 行动 → 输出 ↺                      │    ║ │
│  ║   └─────────────────────────────────────────────────────────────────────┘    ║ │
│  ║                                      │                                        ║ │
│  ║           ┌──────────────────────────┼──────────────────────────┐            ║ │
│  ║           ▼                          ▼                          ▼            ║ │
│  ║   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐         ║ │
│  ║   │  工具系统   │          │  记忆系统   │          │  模型网关   │         ║ │
│  ║   │   Tools     │          │   Memory    │          │ LLM Gateway │         ║ │
│  ║   └─────────────┘          └─────────────┘          └─────────────┘         ║ │
│  ║                                                                               ║ │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝ │
│                                                                                     │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗ │
│  ║                              数据存储层                                        ║ │
│  ║   [PostgreSQL]  [Redis]  [Qdrant向量库]  [MinIO对象存储]                      ║ │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝ │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心集成点

### 2.1 集成点概览

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               核心集成点                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                            集成点 1: 配置转换                                │   │
│  │  工作台可视化配置 ──────────▶ Agent Core 执行配置                            │   │
│  │                                                                              │   │
│  │  • Workflow JSON (节点+边) → AgentConfig                                     │   │
│  │  • 节点配置 → System Prompt / Tools / Memory Config                         │   │
│  │  • 执行逻辑 → Main Loop 执行策略                                            │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                            集成点 2: 执行调用                                │   │
│  │  工作台发起执行 ──────────▶ Agent Core 处理请求                              │   │
│  │                                                                              │   │
│  │  • 测试运行 → AgentEngine.run()                                             │   │
│  │  • 单步调试 → AgentEngine.step()                                            │   │
│  │  • 生产执行 → 部署的 Agent 实例                                             │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                            集成点 3: 事件回传 (运行时状态可视化)            │   │
│  │  Agent Core 执行事件 ──────────▶ 工作台接收展示                              │   │
│  │                                                                              │   │
│  │  通过 ExecutionTracer + WebSocket 实现实时状态推送:                         │   │
│  │  • NODE_ENTER/EXIT → 节点执行高亮 (蓝色脉冲/绿色完成)                       │   │
│  │  • STATE_UPDATE → 状态面板实时更新 (messages, context, iteration)           │   │
│  │  • LLM_STREAM_CHUNK → LLM 流式输出实时展示                                  │   │
│  │  • TOOL_CALL/RESULT → 工具调用参数和结果展示                                │   │
│  │  • Token统计 → 成本计算展示                                                 │   │
│  │  • 状态快照 → Time Travel 调试 (点击历史事件查看当时状态)                   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                            集成点 4: 数据共享                                │   │
│  │  共享数据模型和存储                                                          │   │
│  │                                                                              │   │
│  │  • Agent配置 → 共用 agents 表                                               │   │
│  │  • 会话记录 → 共用 sessions/messages 表                                     │   │
│  │  • 记忆数据 → 共用 memories 表 + 向量库                                     │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、Code-First 架构设计

### 3.1 核心理念

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          Code-First 架构理念                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  核心原则: 底层是 Python 代码，React Flow 只是代码的可视化渲染                      │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                              │   │
│  │   ┌───────────────────┐        解析         ┌───────────────────┐          │   │
│  │   │   Python 代码      │  ────────────────▶ │     图结构        │          │   │
│  │   │  (LangGraph DSL)   │       Parser       │ (nodes, edges)    │          │   │
│  │   │                    │                    │                   │          │   │
│  │   │  graph.add_node()  │                    │  {nodes: [...],   │          │   │
│  │   │  graph.add_edge()  │                    │   edges: [...]}   │          │   │
│  │   └───────────────────┘                    └───────────────────┘          │   │
│  │            ▲                                         │                     │   │
│  │            │                                         │ 渲染                │   │
│  │            │ 代码生成                                ▼                     │   │
│  │            │ CodeGen                        ┌───────────────────┐          │   │
│  │            │                                │   React Flow      │          │   │
│  │            └─────────────────────────────── │   可视化画布      │          │   │
│  │                                             │                   │          │   │
│  │                                             │  [拖拽] [连接]    │          │   │
│  │                                             └───────────────────┘          │   │
│  │                                                                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  数据流向:                                                                          │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  1. 用户写代码 → 解析 AST → 提取图结构 → React Flow 渲染                           │
│  2. 用户拖拽 UI → 生成代码变更 → 更新 Python 文件                                  │
│  3. 双向实时同步                                                                   │
│                                                                                     │
│  为什么这样设计:                                                                    │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│  ✅ 定制化极高 - 代码可以表达任意复杂逻辑                                          │
│  ✅ 版本控制友好 - Python 代码 Git diff 清晰                                       │
│  ✅ 复用性强 - 函数、类、模块、包都可以复用                                        │
│  ✅ 调试方便 - 标准 Python 调试器、IDE 支持                                        │
│  ✅ 与 LangGraph 原生兼容 - 直接执行，无需转换                                     │
│  ✅ 专业用户友好 - 开发者可以完全用代码                                            │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 代码即配置

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           代码即配置 (Code as Config)                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  传统方式 (Visual-First):                     我们的方式 (Code-First):              │
│  ─────────────────────────────                ─────────────────────────────         │
│                                                                                     │
│  ┌─────────────────────┐                      ┌─────────────────────────────┐       │
│  │  UI 拖拽            │                      │  # agent_research.py        │       │
│  │     ↓               │                      │                             │       │
│  │  JSON 配置          │                      │  from langgraph.graph import│       │
│  │     ↓               │                      │      StateGraph, END        │       │
│  │  转换器 (Converter) │                      │                             │       │
│  │     ↓               │                      │  graph = StateGraph(State)  │       │
│  │  执行配置           │                      │  graph.add_node("search",   │       │
│  │     ↓               │                      │      search_web)            │       │
│  │  运行               │                      │  graph.add_node("analyze",  │       │
│  └─────────────────────┘                      │      analyze_results)       │       │
│                                               │  graph.add_edge("search",   │       │
│  问题:                                        │      "analyze")             │       │
│  • JSON 可读性差                              │  graph.add_edge("analyze",  │       │
│  • 复杂逻辑难以表达                           │      END)                   │       │
│  • 需要额外转换层                             │                             │       │
│  • 调试困难                                   │  # 这就是执行配置！         │       │
│  • 版本控制不友好                             │  # 无需转换，直接运行       │       │
│                                               └─────────────────────────────┘       │
│                                                                                     │
│                                               优势:                                 │
│                                               • 代码即文档                         │
│                                               • 直接执行，零转换                   │
│                                               • IDE 智能提示                       │
│                                               • 完整调试能力                       │
│                                               • Git 友好                           │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 双向编辑架构

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             双向编辑架构                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           工作台界面                                         │   │
│  │  ┌───────────────────────────────┬───────────────────────────────┐          │   │
│  │  │                               │                               │          │   │
│  │  │      代码编辑器               │       可视化画布              │          │   │
│  │  │     (Monaco Editor)           │      (React Flow)             │          │   │
│  │  │                               │                               │          │   │
│  │  │  from langgraph.graph import  │    ┌─────┐      ┌─────┐      │          │   │
│  │  │      StateGraph, END          │    │search│─────▶│analyze│    │          │   │
│  │  │                               │    └─────┘      └──┬──┘      │          │   │
│  │  │  graph = StateGraph(State)    │                    │          │          │   │
│  │  │  graph.add_node("search",..)  │                    ▼          │          │   │
│  │  │  graph.add_node("analyze",..) │               ┌─────┐         │          │   │
│  │  │  graph.add_edge(...)          │               │ END │         │          │   │
│  │  │                               │               └─────┘         │          │   │
│  │  │                               │                               │          │   │
│  │  └───────────────────────────────┴───────────────────────────────┘          │   │
│  │                    ▲                               │                         │   │
│  │                    │         实时同步              │                         │   │
│  │                    └───────────────────────────────┘                         │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  同步机制:                                                                          │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                     │
│  代码 → 可视化:                                                                     │
│  1. 监听代码文件变更                                                               │
│  2. 解析 Python AST，提取 StateGraph 结构                                          │
│  3. 转换为 React Flow 格式 {nodes: [], edges: []}                                  │
│  4. 更新画布渲染                                                                   │
│                                                                                     │
│  可视化 → 代码:                                                                     │
│  1. 监听 UI 操作 (添加节点、连接边、删除等)                                        │
│  2. 生成对应的 Python 代码片段                                                     │
│  3. 使用 AST 重写技术，精准修改代码                                                │
│  4. 保留用户的代码格式和注释                                                       │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 代码解析器实现

```python
# backend/studio/parser/graph_parser.py

import ast
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class ParsedNode:
    """解析出的节点"""
    id: str
    name: str
    func_name: str
    line_number: int
    
@dataclass  
class ParsedEdge:
    """解析出的边"""
    source: str
    target: str
    condition: Optional[str] = None
    line_number: int = 0

@dataclass
class ParsedGraph:
    """解析出的图结构"""
    nodes: List[ParsedNode]
    edges: List[ParsedEdge]
    state_class: Optional[str]
    source_file: str

class LangGraphParser:
    """LangGraph 代码解析器"""
    
    def parse_file(self, file_path: str) -> ParsedGraph:
        """解析 Python 文件，提取图结构"""
        with open(file_path, 'r') as f:
            source = f.read()
        return self.parse_source(source, file_path)
    
    def parse_source(self, source: str, file_path: str = "") -> ParsedGraph:
        """解析源代码"""
        tree = ast.parse(source)
        
        nodes = []
        edges = []
        state_class = None
        
        for node in ast.walk(tree):
            # 查找 StateGraph 实例化
            if isinstance(node, ast.Call):
                if self._is_stategraph_call(node):
                    state_class = self._extract_state_class(node)
                    
            # 查找 add_node 调用
            if isinstance(node, ast.Call):
                if self._is_add_node_call(node):
                    parsed_node = self._parse_add_node(node)
                    if parsed_node:
                        nodes.append(parsed_node)
                        
            # 查找 add_edge 调用
            if isinstance(node, ast.Call):
                if self._is_add_edge_call(node):
                    parsed_edge = self._parse_add_edge(node)
                    if parsed_edge:
                        edges.append(parsed_edge)
                        
            # 查找 add_conditional_edges 调用
            if isinstance(node, ast.Call):
                if self._is_conditional_edge_call(node):
                    parsed_edges = self._parse_conditional_edges(node)
                    edges.extend(parsed_edges)
        
        return ParsedGraph(
            nodes=nodes,
            edges=edges,
            state_class=state_class,
            source_file=file_path
        )
    
    def _is_add_node_call(self, node: ast.Call) -> bool:
        """检查是否是 graph.add_node() 调用"""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr == "add_node"
        return False
    
    def _parse_add_node(self, node: ast.Call) -> Optional[ParsedNode]:
        """解析 add_node 调用"""
        if len(node.args) >= 2:
            node_name = ast.literal_eval(node.args[0])
            func_name = node.args[1].id if isinstance(node.args[1], ast.Name) else str(node.args[1])
            return ParsedNode(
                id=node_name,
                name=node_name,
                func_name=func_name,
                line_number=node.lineno
            )
        return None
    
    # ... 更多解析方法

def to_react_flow_format(parsed: ParsedGraph) -> Dict[str, Any]:
    """转换为 React Flow 格式"""
    nodes = []
    edges = []
    
    # 自动布局位置计算
    for i, node in enumerate(parsed.nodes):
        nodes.append({
            "id": node.id,
            "type": "custom",  # 自定义节点类型
            "position": {"x": 100 + (i % 3) * 250, "y": 100 + (i // 3) * 150},
            "data": {
                "label": node.name,
                "func": node.func_name,
                "line": node.line_number
            }
        })
    
    for edge in parsed.edges:
        edges.append({
            "id": f"{edge.source}-{edge.target}",
            "source": edge.source,
            "target": edge.target,
            "label": edge.condition,
            "type": "smoothstep"
        })
    
    return {"nodes": nodes, "edges": edges}
```

### 3.5 代码生成器实现

```python
# backend/studio/codegen/graph_codegen.py

from typing import Dict, List, Any
import ast
import astor  # AST to source code

class LangGraphCodeGen:
    """LangGraph 代码生成器"""
    
    def __init__(self, source_file: str):
        self.source_file = source_file
        with open(source_file, 'r') as f:
            self.source = f.read()
        self.tree = ast.parse(self.source)
    
    def add_node(self, node_name: str, func_name: str) -> str:
        """添加节点，返回更新后的代码"""
        # 找到最后一个 add_node 调用的位置
        insert_line = self._find_last_add_node_line()
        
        # 生成新的代码行
        new_line = f'graph.add_node("{node_name}", {func_name})'
        
        # 插入代码
        lines = self.source.split('\n')
        lines.insert(insert_line, new_line)
        
        return '\n'.join(lines)
    
    def add_edge(self, source: str, target: str) -> str:
        """添加边"""
        insert_line = self._find_last_add_edge_line()
        new_line = f'graph.add_edge("{source}", "{target}")'
        
        lines = self.source.split('\n')
        lines.insert(insert_line, new_line)
        
        return '\n'.join(lines)
    
    def remove_node(self, node_name: str) -> str:
        """删除节点"""
        # 使用 AST 重写，删除对应的 add_node 调用
        class NodeRemover(ast.NodeTransformer):
            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call):
                    if self._is_add_node_for(node.value, node_name):
                        return None  # 删除此节点
                return node
        
        new_tree = NodeRemover().visit(self.tree)
        return astor.to_source(new_tree)
    
    def update_from_react_flow(self, flow_data: Dict[str, Any]) -> str:
        """从 React Flow 数据更新代码"""
        # 比较现有图结构和新的 flow_data
        # 生成增量更新代码
        pass
```

### 3.6 传统配置转换 (兼容模式)

> 注: 以下为兼容旧版 JSON 配置的转换逻辑，新项目推荐使用 Code-First

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         配置转换 (兼容模式)                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  如果用户导入旧版 JSON 配置，转换为 Python 代码:                                    │
│                                                                                     │
│  JSON 输入:                              生成的 Python 代码:                        │
│  ────────────────────────────            ────────────────────────────               │
│  {                                       from langgraph.graph import                │
│    "nodes": [                                StateGraph, START, END                 │
│      {"id": "n1", "type": "llm"},                                                   │
│      {"id": "n2", "type": "tool"}        class State(TypedDict):                   │
│    ],                                        messages: list                         │
│    "edges": [                                                                       │
│      {"from": "n1", "to": "n2"}          graph = StateGraph(State)                 │
│    ]                                     graph.add_node("n1", llm_node)            │
│  }                                       graph.add_node("n2", tool_node)           │
│                                          graph.add_edge(START, "n1")               │
│                                          graph.add_edge("n1", "n2")                │
│                                          graph.add_edge("n2", END)                 │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 节点类型映射

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              节点类型 → Agent Core 映射                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  工作台节点                        映射到 Agent Core                                │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                     │
│  📥 用户输入节点                                                                    │
│  ├─ UserInput         →   Main Loop 的入口点                                       │
│  ├─ Webhook           →   HTTP Trigger + Main Loop                                 │
│  └─ Schedule          →   定时任务 + Main Loop                                     │
│                                                                                     │
│  🧠 Agent节点                                                                       │
│  ├─ LLMNode           →   LLMGateway.chat()                                        │
│  │   • model           →   model 配置                                              │
│  │   • prompt          →   组装到上下文                                            │
│  │   • temperature     →   generation 配置                                         │
│  │                                                                                 │
│  ├─ IntentNode        →   LLMGateway.chat() + 意图解析                             │
│  │   • intents         →   转换为分类 prompt                                       │
│  │   • routes          →   生成分支逻辑                                            │
│  │                                                                                 │
│  ├─ RAGNode           →   MemoryRetriever.retrieve()                               │
│  │   • knowledge_base  →   向量库 collection                                       │
│  │   • top_k           →   检索数量                                                │
│  │                                                                                 │
│  └─ AgentCallNode     →   A2A 调用                                                 │
│      • agent_id        →   目标 Agent                                              │
│      • input_mapping   →   参数映射                                                │
│                                                                                     │
│  🔧 工具节点                                                                        │
│  ├─ HTTPNode          →   ToolExecutor.execute("http_request", ...)                │
│  ├─ DatabaseNode      →   ToolExecutor.execute("query_db", ...)                    │
│  ├─ CodeNode          →   ToolExecutor.execute("run_code", ...)                    │
│  ├─ FileNode          →   ToolExecutor.execute("file_op", ...)                     │
│  └─ MCPNode           →   ToolExecutor.execute_mcp(...)                            │
│                                                                                     │
│  ⚡ 逻辑节点                                                                        │
│  ├─ ConditionNode     →   ExecutionPlan.branches                                   │
│  ├─ LoopNode          →   ExecutionPlan.loops                                      │
│  ├─ ParallelNode      →   asyncio.gather() 并行执行                                │
│  └─ WaitNode          →   Human-in-the-loop 等待                                   │
│                                                                                     │
│  📤 输出节点                                                                        │
│  ├─ ResponseNode      →   流式返回给用户                                           │
│  ├─ NotifyNode        →   ToolExecutor.execute("send_notification", ...)           │
│  └─ StoreNode         →   MemoryManager.store() / DB写入                           │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 转换器实现

```python
# backend/studio/orchestrator/converter.py

from typing import Dict, List, Any
from pydantic import BaseModel

class WorkflowDefinition(BaseModel):
    """工作台工作流定义"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, str]]
    variables: Dict[str, Any] = {}

class AgentConfig(BaseModel):
    """Agent Core 执行配置"""
    agent_id: str
    name: str
    system_prompt: str
    model: str
    tools: List[str]
    memory_config: Dict[str, Any]
    max_iterations: int = 10

class ExecutionPlan(BaseModel):
    """执行计划"""
    steps: List[Dict[str, Any]]
    branches: List[Dict[str, Any]] = []
    loops: List[Dict[str, Any]] = []

class WorkflowConverter:
    """工作流配置转换器"""
    
    def __init__(self, tool_registry, agent_registry):
        self.tools = tool_registry
        self.agents = agent_registry
    
    def convert(self, workflow: WorkflowDefinition) -> tuple[AgentConfig, ExecutionPlan]:
        """
        将工作台配置转换为 Agent Core 可执行配置
        
        转换步骤:
        1. 解析节点，提取配置
        2. 构建执行图
        3. 生成 AgentConfig
        4. 生成 ExecutionPlan
        """
        # 1. 构建节点索引
        node_map = {node["id"]: node for node in workflow.nodes}
        
        # 2. 构建邻接表
        adjacency = self._build_adjacency(workflow.edges)
        
        # 3. 提取 System Prompt (从 LLM 节点)
        system_prompt = self._extract_system_prompt(node_map)
        
        # 4. 收集工具列表
        tools = self._collect_tools(node_map)
        
        # 5. 提取模型配置
        model_config = self._extract_model_config(node_map)
        
        # 6. 生成执行计划
        execution_plan = self._generate_execution_plan(
            node_map, adjacency, workflow.variables
        )
        
        # 构建 AgentConfig
        agent_config = AgentConfig(
            agent_id=workflow.id,
            name=workflow.name,
            system_prompt=system_prompt,
            model=model_config.get("model", "claude-3-5-sonnet-20241022"),
            tools=tools,
            memory_config=self._extract_memory_config(node_map),
        )
        
        return agent_config, execution_plan
    
    def _extract_system_prompt(self, node_map: Dict) -> str:
        """从 LLM 节点提取 System Prompt"""
        prompts = []
        
        for node in node_map.values():
            if node["type"] == "llm" and node.get("config", {}).get("system_prompt"):
                prompts.append(node["config"]["system_prompt"])
        
        return "\n\n".join(prompts) if prompts else ""
    
    def _collect_tools(self, node_map: Dict) -> List[str]:
        """收集所有使用的工具"""
        tools = set()
        
        for node in node_map.values():
            node_type = node["type"]
            
            # 工具节点直接添加
            if node_type == "http":
                tools.add("http_request")
            elif node_type == "database":
                tools.add("query_db")
            elif node_type == "code":
                tools.add("run_code")
            elif node_type == "file":
                tools.add("file_op")
            elif node_type == "mcp":
                tools.add(f"mcp:{node['config']['tool_name']}")
        
        return list(tools)
    
    def _generate_execution_plan(
        self,
        node_map: Dict,
        adjacency: Dict,
        variables: Dict,
    ) -> ExecutionPlan:
        """生成执行计划"""
        steps = []
        branches = []
        loops = []
        
        # 拓扑排序获取执行顺序
        sorted_nodes = self._topological_sort(node_map, adjacency)
        
        for node_id in sorted_nodes:
            node = node_map[node_id]
            
            if node["type"] == "condition":
                # 条件分支
                branches.append({
                    "node_id": node_id,
                    "conditions": node["config"]["conditions"],
                    "routes": self._get_branch_routes(node_id, adjacency),
                })
            elif node["type"] == "loop":
                # 循环
                loops.append({
                    "node_id": node_id,
                    "condition": node["config"]["condition"],
                    "body_nodes": node["config"]["body_nodes"],
                })
            else:
                # 普通步骤
                steps.append({
                    "node_id": node_id,
                    "type": node["type"],
                    "config": node["config"],
                })
        
        return ExecutionPlan(
            steps=steps,
            branches=branches,
            loops=loops,
        )
```

---

## 四、执行调用集成

### 4.1 调用链路

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               执行调用链路                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  工作台                          Studio Service                   Agent Core        │
│                                                                                     │
│  ┌─────────┐                                                                        │
│  │ 调试测试 │                                                                        │
│  │  界面   │                                                                        │
│  └────┬────┘                                                                        │
│       │ 1. 发起测试运行                                                             │
│       ▼                                                                             │
│  ┌─────────────────────────────────────────┐                                       │
│  │     POST /api/v1/studio/test/run        │                                       │
│  │     {                                   │                                       │
│  │       "workflow_id": "...",             │                                       │
│  │       "input": {"message": "..."},      │                                       │
│  │       "variables": {...}                │                                       │
│  │     }                                   │                                       │
│  └────────────────┬────────────────────────┘                                       │
│                   │                                                                 │
│                   │ 2. 获取工作流配置                                               │
│                   ▼                                                                 │
│            ┌──────────────┐                                                        │
│            │ TestRunner   │                                                        │
│            │  Service     │                                                        │
│            └──────┬───────┘                                                        │
│                   │                                                                 │
│                   │ 3. 转换配置                                                     │
│                   ▼                                                                 │
│            ┌──────────────┐                                                        │
│            │  Converter   │                                                        │
│            │  (配置转换)  │                                                        │
│            └──────┬───────┘                                                        │
│                   │                                                                 │
│                   │ 4. AgentConfig + ExecutionPlan                                 │
│                   ▼                                                                 │
│            ┌──────────────────────────────────────────────────────────────┐        │
│            │                      AgentEngine                              │        │
│            │  ┌────────────────────────────────────────────────────────┐  │        │
│            │  │                    Main Loop                            │  │        │
│            │  │   5. 组装上下文 ─▶ ContextManager.build()              │  │        │
│            │  │   6. 调用模型   ─▶ LLMGateway.chat()                   │  │        │
│            │  │   7. 执行工具   ─▶ ToolExecutor.execute()              │  │        │
│            │  │   8. 更新记忆   ─▶ MemoryManager.process()             │  │        │
│            │  └────────────────────────────────────────────────────────┘  │        │
│            └──────────────────────────────────────────────────────────────┘        │
│                   │                                                                 │
│                   │ 9. 流式返回执行事件 (SSE)                                       │
│                   ▼                                                                 │
│  ┌─────────────────────────────────────────┐                                       │
│  │     SSE Stream                          │                                       │
│  │     event: trace                        │                                       │
│  │     data: {                             │                                       │
│  │       "type": "llm_call",               │                                       │
│  │       "duration_ms": 1234,              │                                       │
│  │       "tokens": {...}                   │                                       │
│  │     }                                   │                                       │
│  └────────────────┬────────────────────────┘                                       │
│                   │                                                                 │
│                   │ 10. 实时展示                                                    │
│                   ▼                                                                 │
│  ┌─────────┐                                                                        │
│  │ 执行追踪 │                                                                        │
│  │  展示   │                                                                        │
│  └─────────┘                                                                        │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 TestRunner 实现

```python
# backend/studio/test_runner/runner.py

from typing import AsyncGenerator
from pydantic import BaseModel

class TestRunRequest(BaseModel):
    workflow_id: str
    input: dict
    variables: dict = {}

class TraceEvent(BaseModel):
    """执行追踪事件"""
    type: str  # context_build, llm_call, tool_call, memory_update, done, error
    node_id: str | None = None
    timestamp: float
    duration_ms: int | None = None
    data: dict = {}

class TestRunner:
    """测试运行器 - 连接工作台与 Agent Core"""
    
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        converter: WorkflowConverter,
        agent_engine_factory: AgentEngineFactory,
    ):
        self.workflows = workflow_repo
        self.converter = converter
        self.engine_factory = agent_engine_factory
    
    async def run(
        self,
        request: TestRunRequest,
    ) -> AsyncGenerator[TraceEvent, None]:
        """
        执行测试运行
        
        1. 获取工作流配置
        2. 转换为执行配置
        3. 创建临时 AgentEngine
        4. 执行并流式返回追踪事件
        """
        # 1. 获取工作流
        workflow = await self.workflows.get(request.workflow_id)
        if not workflow:
            yield TraceEvent(
                type="error",
                timestamp=time.time(),
                data={"error": "Workflow not found"}
            )
            return
        
        # 2. 转换配置
        try:
            agent_config, execution_plan = self.converter.convert(
                workflow.definition
            )
        except Exception as e:
            yield TraceEvent(
                type="error",
                timestamp=time.time(),
                data={"error": f"Config conversion failed: {e}"}
            )
            return
        
        # 3. 创建临时 Agent Engine (带追踪)
        engine = self.engine_factory.create(
            config=agent_config,
            execution_plan=execution_plan,
            enable_tracing=True,  # 启用追踪
        )
        
        # 4. 执行并转发追踪事件
        try:
            async for event in engine.run_with_trace(
                user_input=request.input.get("message", ""),
                session_id=f"test_{request.workflow_id}_{time.time()}",
                variables=request.variables,
            ):
                yield self._convert_engine_event(event)
        except Exception as e:
            yield TraceEvent(
                type="error",
                timestamp=time.time(),
                data={"error": str(e)}
            )
    
    def _convert_engine_event(self, engine_event) -> TraceEvent:
        """将 Agent Engine 事件转换为追踪事件"""
        return TraceEvent(
            type=engine_event.type,
            node_id=engine_event.node_id,
            timestamp=engine_event.timestamp,
            duration_ms=engine_event.duration_ms,
            data={
                "content": engine_event.content,
                "tokens": engine_event.tokens,
                "tool_call": engine_event.tool_call,
                "tool_result": engine_event.tool_result,
            }
        )
```

### 4.3 Agent Engine 扩展 (支持追踪)

```python
# backend/core/agent/engine.py (扩展)

class AgentEngine:
    """Agent 执行引擎 (扩展追踪能力)"""
    
    async def run_with_trace(
        self,
        user_input: str,
        session_id: str,
        variables: dict = {},
    ) -> AsyncGenerator[EngineEvent, None]:
        """
        带追踪的执行模式 - 供工作台调试使用
        """
        iteration = 0
        start_time = time.time()
        
        while iteration < self.config.max_iterations:
            iteration += 1
            
            # 追踪: 上下文组装
            ctx_start = time.time()
            context = await self.context.build(
                session_id=session_id,
                user_input=user_input,
                system_prompt=self.config.system_prompt,
            )
            yield EngineEvent(
                type="context_build",
                timestamp=ctx_start,
                duration_ms=int((time.time() - ctx_start) * 1000),
                data={
                    "total_tokens": context.total_tokens,
                    "breakdown": {
                        "system": self.counter.count(self.config.system_prompt),
                        "history": context.history_tokens,
                        "memory": context.memory_tokens,
                    }
                }
            )
            
            # 追踪: LLM 调用
            llm_start = time.time()
            response = await self.llm.chat(
                messages=context.messages,
                tools=self.tools.get_definitions(),
                model=self.config.model,
                stream=True,
            )
            
            full_response = ""
            tool_calls = []
            input_tokens = 0
            output_tokens = 0
            
            async for chunk in response:
                if chunk.type == "text":
                    full_response += chunk.content
                    yield EngineEvent(
                        type="text_chunk",
                        timestamp=time.time(),
                        data={"content": chunk.content}
                    )
                elif chunk.type == "tool_call":
                    tool_calls.append(chunk.tool_call)
                elif chunk.type == "usage":
                    input_tokens = chunk.input_tokens
                    output_tokens = chunk.output_tokens
            
            yield EngineEvent(
                type="llm_call",
                timestamp=llm_start,
                duration_ms=int((time.time() - llm_start) * 1000),
                data={
                    "model": self.config.model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "has_tool_calls": len(tool_calls) > 0,
                }
            )
            
            # 追踪: 工具调用
            if tool_calls:
                for tool_call in tool_calls:
                    tool_start = time.time()
                    
                    yield EngineEvent(
                        type="tool_call_start",
                        timestamp=tool_start,
                        data={
                            "tool": tool_call.name,
                            "args": tool_call.arguments,
                        }
                    )
                    
                    result = await self.tools.execute(
                        name=tool_call.name,
                        arguments=tool_call.arguments,
                        session_id=session_id,
                    )
                    
                    yield EngineEvent(
                        type="tool_call_end",
                        timestamp=tool_start,
                        duration_ms=int((time.time() - tool_start) * 1000),
                        data={
                            "tool": tool_call.name,
                            "success": result.success,
                            "output": result.output[:500],  # 截断
                            "error": result.error,
                        }
                    )
                    
                    await self.context.add_tool_result(
                        session_id=session_id,
                        tool_call=tool_call,
                        result=result,
                    )
                
                user_input = None
                continue
            
            # 追踪: 记忆更新
            if full_response:
                memory_start = time.time()
                await self.memory.process(
                    session_id=session_id,
                    content=full_response,
                )
                yield EngineEvent(
                    type="memory_update",
                    timestamp=memory_start,
                    duration_ms=int((time.time() - memory_start) * 1000),
                )
            
            # 完成
            yield EngineEvent(
                type="done",
                timestamp=start_time,
                duration_ms=int((time.time() - start_time) * 1000),
                data={
                    "iterations": iteration,
                    "response": full_response,
                }
            )
            break
```

### 4.3 运行时状态可视化集成

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           运行时状态可视化集成架构                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         工作台前端 (React)                                   │   │
│  │                                                                              │   │
│  │   ┌────────────────┐  ┌────────────────────┐  ┌──────────────────────┐      │   │
│  │   │  执行流程       │  │   当前状态          │  │   执行日志           │      │   │
│  │   │  (节点高亮)     │  │   (实时更新)        │  │   (WebSocket流)      │      │   │
│  │   ├────────────────┤  ├────────────────────┤  ├──────────────────────┤      │   │
│  │   │ [入口] ✓       │  │ messages: 3        │  │ ▶ 进入节点: think    │      │   │
│  │   │   ↓            │  │ context: {...}     │  │ ⚡ 调用: search      │      │   │
│  │   │ [思考] 🔵      │  │ iteration: 2       │  │ 💬 LLM: 根据搜索...  │      │   │
│  │   │   ↓            │  │                    │  │ ✓ 完成: think 2.3s  │      │   │
│  │   │ [执行] ○       │  │                    │  │                      │      │   │
│  │   └────────────────┘  └────────────────────┘  └──────────────────────┘      │   │
│  │                                                                              │   │
│  └──────────────────────────────────────┬───────────────────────────────────────┘   │
│                                         │ WebSocket                                 │
│                                         ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                      执行追踪服务 (ExecutionTracer)                          │   │
│  │                                                                              │   │
│  │   事件类型:                                                                  │   │
│  │   ├─ NODE_ENTER / NODE_EXIT     节点进入/退出 → 流程图高亮                  │   │
│  │   ├─ STATE_UPDATE               状态变化 → 状态面板更新                     │   │
│  │   ├─ LLM_REQUEST / LLM_STREAM   LLM调用 → 思考过程展示                      │   │
│  │   ├─ TOOL_CALL / TOOL_RESULT    工具调用 → 调用详情展示                     │   │
│  │   ├─ CHECKPOINT_SAVE            检查点 → 可回溯状态                         │   │
│  │   └─ ERROR                      错误 → 错误定位和展示                       │   │
│  │                                                                              │   │
│  └──────────────────────────────────────┬───────────────────────────────────────┘   │
│                                         │ emit()                                    │
│                                         ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                          AgentEngine (Agent Core)                            │   │
│  │                                                                              │   │
│  │   Main Loop 中集成追踪:                                                      │   │
│  │   ┌──────────────────────────────────────────────────────────────────────┐  │   │
│  │   │  async for state in graph.astream(input):                             │  │   │
│  │   │      # 进入节点                                                       │  │   │
│  │   │      await tracer.node_enter(node_id, node_name, state)               │  │   │
│  │   │                                                                       │  │   │
│  │   │      # 执行节点逻辑...                                                │  │   │
│  │   │      result = await node_func(state)                                  │  │   │
│  │   │                                                                       │  │   │
│  │   │      # 退出节点                                                       │  │   │
│  │   │      await tracer.node_exit(node_id, node_name, result)               │  │   │
│  │   └──────────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

#### WebSocket 端点

```python
# backend/api/routes/execution.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.execution_tracer import ExecutionTracer

router = APIRouter()

@router.websocket("/ws/execution/{session_id}")
async def execution_websocket(websocket: WebSocket, session_id: str):
    """执行状态 WebSocket - 实时推送执行事件到前端"""
    await websocket.accept()
    
    tracer = get_or_create_tracer(session_id)
    queue = tracer.subscribe()
    
    try:
        while True:
            event = await queue.get()
            await websocket.send_json({
                "id": event.id,
                "type": event.type.value,
                "timestamp": event.timestamp.isoformat(),
                "node_id": event.node_id,
                "node_name": event.node_name,
                "data": event.data,
                "duration_ms": event.duration_ms,
                "state_snapshot": event.state_snapshot  # 用于 Time Travel
            })
    except WebSocketDisconnect:
        tracer.unsubscribe(queue)
```

#### 前端集成

```typescript
// frontend/src/hooks/useExecutionTracer.ts

import { useEffect, useState } from 'react';
import { useWebSocket } from './useWebSocket';

interface TraceEvent {
  id: string;
  type: 'node_enter' | 'node_exit' | 'state_update' | 'llm_stream_chunk' | 
        'tool_call' | 'tool_result' | 'error';
  timestamp: string;
  node_id?: string;
  node_name?: string;
  data: Record<string, any>;
  duration_ms?: number;
  state_snapshot?: Record<string, any>;
}

export function useExecutionTracer(sessionId: string) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [currentState, setCurrentState] = useState<Record<string, any>>({});
  
  const { lastMessage } = useWebSocket(`/ws/execution/${sessionId}`);
  
  useEffect(() => {
    if (lastMessage) {
      const event = JSON.parse(lastMessage.data) as TraceEvent;
      setEvents(prev => [...prev, event]);
      
      // 更新当前节点高亮
      if (event.type === 'node_enter') {
        setCurrentNode(event.node_id || null);
      } else if (event.type === 'node_exit') {
        setCurrentNode(null);
      }
      
      // 更新状态快照
      if (event.state_snapshot) {
        setCurrentState(event.state_snapshot);
      }
    }
  }, [lastMessage]);
  
  // Time Travel: 查看历史状态
  const getStateAt = (eventId: string) => {
    const event = events.find(e => e.id === eventId);
    return event?.state_snapshot || null;
  };
  
  return { events, currentNode, currentState, getStateAt };
}
```

---

## 五、数据模型共享

### 5.1 共享数据表

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               数据模型共享设计                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                          Agent Core 数据模型                                 │   │
│  │                                                                              │   │
│  │   users ─────────▶ agents ─────────▶ sessions ─────────▶ messages          │   │
│  │                      │                    │                                  │   │
│  │                      │                    └─────────▶ tool_calls            │   │
│  │                      │                                                       │   │
│  │                      └─────────▶ memories                                    │   │
│  │                                                                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                             │
│                                       │ 扩展                                        │
│                                       ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                          工作台扩展数据模型                                   │   │
│  │                                                                              │   │
│  │   agents ◀────────── workflows ─────────▶ workflow_versions                 │   │
│  │      │                    │                                                  │   │
│  │      │                    └─────────▶ deployments                            │   │
│  │      │                                                                       │   │
│  │      └─────────▶ prompt_versions                                             │   │
│  │                                                                              │   │
│  │   templates (独立)                                                           │   │
│  │                                                                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  关系说明:                                                                          │
│  • agents 表被两边共用，工作台创建，Agent Core 执行                                 │
│  • workflows 属于 agents，定义可视化编排                                            │
│  • workflow_versions 记录编排历史                                                   │
│  • deployments 记录部署状态，关联到特定版本                                         │
│  • prompt_versions 记录提示词历史                                                   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 数据同步机制

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               数据同步机制                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  场景 1: 工作台创建/编辑 Agent                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                     │
│  工作台                                              Agent Core                     │
│  ┌──────────────┐                                   ┌──────────────┐               │
│  │ 保存工作流   │ ───▶ workflows 表                 │              │               │
│  │              │ ───▶ 编译配置 ───▶ agents 表     │ 读取执行配置 │               │
│  └──────────────┘                   (compiled_config)└──────────────┘               │
│                                                                                     │
│  场景 2: Agent Core 执行产生数据                                                    │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                     │
│  Agent Core                                         工作台                          │
│  ┌──────────────┐                                   ┌──────────────┐               │
│  │ 执行对话     │ ───▶ sessions/messages 表        │ 查看执行历史 │               │
│  │ 存储记忆     │ ───▶ memories 表 + 向量库        │ 查看记忆内容 │               │
│  └──────────────┘                                   └──────────────┘               │
│                                                                                     │
│  场景 3: 部署同步                                                                   │
│  ─────────────────────────────────────────────────────────────────────────────────  │
│                                                                                     │
│  工作台                               部署服务                   Agent Core         │
│  ┌──────────────┐                    ┌──────────────┐           ┌──────────────┐   │
│  │ 发起部署     │ ──────────────────▶│ 创建部署记录 │──────────▶│ 加载配置     │   │
│  │ workflow_v1  │                    │ deployments  │           │ 启动实例     │   │
│  └──────────────┘                    └──────────────┘           └──────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、API 边界设计

### 6.1 API 职责划分

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               API 边界设计                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  /api/v1                                                                            │
│  │                                                                                  │
│  ├─ /studio/                      # 工作台专属 API                                  │
│  │   ├─ /creator/                 # 对话式创建                                      │
│  │   │   └─ POST /chat            # 对话创建Agent                                   │
│  │   │                                                                              │
│  │   ├─ /workflows/               # 工作流管理                                      │
│  │   │   ├─ GET    /              # 列表                                            │
│  │   │   ├─ POST   /              # 创建                                            │
│  │   │   ├─ PUT    /{id}          # 更新                                            │
│  │   │   ├─ POST   /{id}/compile  # 编译为执行配置                                  │
│  │   │   └─ POST   /{id}/validate # 验证工作流                                      │
│  │   │                                                                              │
│  │   ├─ /test/                    # 测试运行                                        │
│  │   │   ├─ POST   /run           # 运行测试 (SSE)                                  │
│  │   │   └─ POST   /run-step      # 单步运行                                        │
│  │   │                                                                              │
│  │   ├─ /prompts/                 # 提示词管理                                      │
│  │   │   ├─ GET    /{agent_id}/versions                                            │
│  │   │   └─ POST   /{agent_id}/versions                                            │
│  │   │                                                                              │
│  │   ├─ /deploy/                  # 部署管理                                        │
│  │   │   ├─ POST   /              # 创建部署                                        │
│  │   │   ├─ PUT    /{id}/stop     # 停止                                            │
│  │   │   └─ PUT    /{id}/restart  # 重启                                            │
│  │   │                                                                              │
│  │   └─ /templates/               # 模板市场                                        │
│  │       ├─ GET    /              # 搜索模板                                        │
│  │       └─ POST   /{id}/use      # 使用模板                                        │
│  │                                                                                  │
│  ├─ /agents/                      # Agent 管理 (共用)                               │
│  │   ├─ GET    /                  # 列表                                            │
│  │   ├─ POST   /                  # 创建                                            │
│  │   ├─ GET    /{id}              # 详情                                            │
│  │   ├─ PUT    /{id}              # 更新                                            │
│  │   └─ DELETE /{id}              # 删除                                            │
│  │                                                                                  │
│  ├─ /chat/                        # 对话 API (Agent Core)                           │
│  │   └─ POST   /                  # 发送消息 (SSE流式)                              │
│  │                                                                                  │
│  ├─ /sessions/                    # 会话管理 (Agent Core)                           │
│  │   ├─ GET    /                  # 列表                                            │
│  │   ├─ GET    /{id}/messages     # 消息历史                                        │
│  │   └─ DELETE /{id}              # 删除                                            │
│  │                                                                                  │
│  └─ /memory/                      # 记忆管理 (共用)                                 │
│      ├─ GET    /                  # 列表                                            │
│      ├─ POST   /search            # 搜索                                            │
│      └─ DELETE /{id}              # 删除                                            │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 内部调用接口

```python
# backend/studio/interfaces.py

from abc import ABC, abstractmethod
from typing import AsyncGenerator

class IAgentEngine(ABC):
    """Agent Engine 接口 - 工作台调用 Agent Core"""
    
    @abstractmethod
    async def run(
        self,
        user_input: str,
        session_id: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """执行 Agent"""
        pass
    
    @abstractmethod
    async def run_with_trace(
        self,
        user_input: str,
        session_id: str,
        variables: dict,
    ) -> AsyncGenerator[EngineEvent, None]:
        """带追踪的执行"""
        pass

class IContextManager(ABC):
    """Context Manager 接口"""
    
    @abstractmethod
    async def build(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str,
    ) -> Context:
        """构建上下文"""
        pass

class IToolExecutor(ABC):
    """Tool Executor 接口"""
    
    @abstractmethod
    async def execute(
        self,
        name: str,
        arguments: dict,
        session_id: str,
    ) -> ToolResult:
        """执行工具"""
        pass

class IMemoryManager(ABC):
    """Memory Manager 接口"""
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        session_id: str,
        max_tokens: int,
    ) -> list[MemoryItem]:
        """检索记忆"""
        pass

class ILLMGateway(ABC):
    """LLM Gateway 接口"""
    
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None,
        stream: bool,
    ) -> AsyncGenerator[LLMChunk, None]:
        """调用模型"""
        pass
```

---

## 七、目录结构对照

```
backend/
├── app/                           # 应用入口
│   ├── main.py
│   └── config.py
│
├── api/v1/                        # API 路由
│   ├── chat.py                    # 对话 API (Agent Core)
│   ├── agent.py                   # Agent 管理 (共用)
│   ├── session.py                 # 会话管理 (Agent Core)
│   ├── memory.py                  # 记忆管理 (共用)
│   └── studio.py                  # 工作台 API (新增)
│
├── core/                          # Agent Core (核心引擎)
│   ├── agent/
│   │   ├── engine.py              # Agent 执行引擎
│   │   ├── loop.py                # Main Loop
│   │   └── context.py             # 上下文管理
│   ├── memory/
│   │   ├── manager.py             # 记忆管理
│   │   └── retriever.py           # 记忆检索
│   ├── tool/
│   │   ├── registry.py            # 工具注册
│   │   └── executor.py            # 工具执行
│   └── llm/
│       └── gateway.py             # 模型网关
│
├── studio/                        # 工作台模块 (新增)
│   ├── orchestrator/              # 编排引擎
│   │   ├── engine.py              # 编排执行
│   │   └── converter.py           # 配置转换 (调用 core)
│   ├── creator/                   # 对话创建器
│   │   └── generator.py           # 配置生成 (调用 core.llm)
│   ├── test_runner/               # 测试运行器
│   │   └── runner.py              # 测试执行 (调用 core.agent)
│   ├── deployer/                  # 部署管理器
│   │   └── publisher.py           # 发布 (配置 core.agent)
│   ├── template/                  # 模板管理
│   └── interfaces.py              # 与 Core 的接口定义
│
├── models/                        # 数据模型 (共用)
│   ├── agent.py                   # Agent (共用)
│   ├── session.py                 # Session (Core)
│   ├── message.py                 # Message (Core)
│   ├── memory.py                  # Memory (共用)
│   ├── workflow.py                # Workflow (Studio)
│   ├── deployment.py              # Deployment (Studio)
│   └── template.py                # Template (Studio)
│
└── services/                      # 业务服务
    ├── chat.py                    # 对话服务 (调用 core.agent)
    ├── agent.py                   # Agent 服务 (共用)
    └── studio.py                  # 工作台服务 (调用 studio/*)
```

---

## 八、集成时序图

### 8.1 测试运行时序

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             测试运行时序图                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  前端         StudioAPI      TestRunner       Converter      AgentEngine            │
│   │              │              │                │               │                  │
│   │──POST /test/run─▶│              │                │               │              │
│   │              │──run()────────▶│                │               │              │
│   │              │              │──get workflow──▶│               │              │
│   │              │              │◀─────────────────│               │              │
│   │              │              │──convert()──────▶│               │              │
│   │              │              │◀──AgentConfig────│               │              │
│   │              │              │                  │               │              │
│   │              │              │──────────run_with_trace()───────▶│              │
│   │              │              │                  │               │              │
│   │              │              │                  │    ┌─────────┐│              │
│   │              │              │                  │    │Main Loop││              │
│   │              │              │                  │    └────┬────┘│              │
│   │              │              │                  │         │     │              │
│   │              │              │◀──────TraceEvent: context_build──│              │
│   │◀─SSE event───│◀─────────────│                  │               │              │
│   │              │              │◀──────TraceEvent: llm_call───────│              │
│   │◀─SSE event───│◀─────────────│                  │               │              │
│   │              │              │◀──────TraceEvent: tool_call──────│              │
│   │◀─SSE event───│◀─────────────│                  │               │              │
│   │              │              │◀──────TraceEvent: done───────────│              │
│   │◀─SSE done────│◀─────────────│                  │               │              │
│   │              │              │                  │               │              │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 部署时序

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              部署时序图                                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  前端        StudioAPI       Deployer        AgentRepo       AgentEngine            │
│   │              │              │               │               │                   │
│   │──POST /deploy─▶│              │               │               │                 │
│   │              │──deploy()────▶│               │               │                 │
│   │              │              │                │               │                 │
│   │              │              │──1.获取工作流配置───────────────▶│                 │
│   │              │              │◀───────compiled_config─────────│                 │
│   │              │              │                │               │                 │
│   │              │              │──2.验证配置────▶│               │                 │
│   │              │              │◀───ok───────────│               │                 │
│   │              │              │                │               │                 │
│   │              │              │──3.创建/更新Agent配置──────────▶│                 │
│   │              │              │◀───────────────│               │                 │
│   │              │              │                │               │                 │
│   │              │              │──4.生成API端点──│               │                 │
│   │              │              │                │               │                 │
│   │              │              │──5.记录部署────▶│ (deployments) │                 │
│   │              │              │◀───────────────│               │                 │
│   │              │              │                │               │                 │
│   │◀─deployment info─│◀─────────────│               │               │               │
│   │              │              │                │               │                 │
│   │              │              │                │               │                 │
│   │                              │                │               │                 │
│  用户调用 API                    │                │               │                 │
│   │──POST /api/v1/chat─────────────────────────────────────────▶│                 │
│   │                              │                │               │──run()         │
│   │◀──────────────────────────────响应────────────────────────────│                 │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 九、总结

### 集成要点

| 集成点 | 工作台职责 | Agent Core 职责 | 交互方式 |
|--------|-----------|----------------|---------|
| **配置转换** | 可视化编排 → Workflow JSON | 无 | Converter 单向调用 |
| **执行调用** | 发起测试/部署请求 | 执行 Main Loop | 接口调用 + 事件回传 |
| **数据共享** | 管理 workflow/deployment | 管理 session/message | 共享数据库 |
| **API边界** | /studio/* 端点 | /chat/* 端点 | REST + SSE |

### 设计原则

1. **松耦合**: 工作台通过接口调用 Agent Core，不直接依赖内部实现
2. **单向数据流**: 配置从工作台流向 Core，执行数据从 Core 流回工作台
3. **共享基础设施**: 共用数据库、缓存、向量库
4. **独立演进**: 两个模块可以独立开发和部署

---

<div align="center">

**工作台负责设计 · Agent Core 负责执行**

*文档版本: v1.0 | 最后更新: 2026-01-12*

</div>
