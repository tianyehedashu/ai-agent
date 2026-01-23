# 🎛️ 工作台功能实现方案

> **版本**: 1.0.0
> **更新日期**: 2026-01-14
> **说明**: 工作台功能实现指南，包括架构设计、实现步骤和代码示例

---

## 📋 目录

1. [实现架构](#实现架构)
2. [当前状态](#当前状态)
3. [实现步骤](#实现步骤)
4. [核心功能实现](#核心功能实现)
5. [前端实现](#前端实现)
6. [测试与调试](#测试与调试)

---

## 实现架构

### 1.1 整体架构

工作台功能**作为现有项目的一部分**实现，不是独立项目：

```
┌─────────────────────────────────────────────────────────────┐
│                    现有项目结构                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  backend/                                                    │
│  ├── core/                                                   │
│  │   ├── engine/          # Agent 执行引擎 (已有)           │
│  │   ├── studio/          # 工作台核心 (部分实现)           │
│  │   │   ├── workflow.py  # 工作流服务 ✅                   │
│  │   │   ├── codegen.py   # 代码生成 ✅                     │
│  │   │   └── parser.py    # 代码解析 ✅                     │
│  │   └── ...               # 其他核心模块                   │
│  │                                                           │
│  ├── api/v1/                                                │
│  │   └── studio.py         # 工作台API (部分实现) ✅        │
│  │                                                           │
│  └── services/                                              │
│      └── studio.py          # 工作台服务 (待实现) ⚠️         │
│                                                              │
│  frontend/                                                   │
│  ├── src/pages/studio/      # 工作台页面 (部分实现) ⚠️       │
│  └── src/api/studio.ts      # 工作台API客户端 (待实现) ⚠️   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 为什么不需要单独项目？

**✅ 优势**:
1. **共享基础设施**: 共用数据库、缓存、向量库
2. **代码复用**: 直接调用 Agent Core 模块
3. **统一部署**: 一个项目，统一运维
4. **数据一致性**: 共享数据模型，无需同步

**❌ 独立项目的缺点**:
1. 需要额外的服务间通信
2. 数据同步复杂
3. 部署和运维成本高
4. 开发调试不便

---

## 当前状态

### 2.1 已实现功能

| 功能 | 位置 | 状态 | 说明 |
|------|------|------|------|
| **工作流CRUD** | `core/studio/workflow.py` | ✅ 完成 | 创建、查询、更新、删除 |
| **代码解析** | `core/studio/parser.py` | ✅ 完成 | Python代码 → React Flow格式 |
| **代码生成** | `core/studio/codegen.py` | ✅ 完成 | React Flow格式 → Python代码 |
| **版本管理** | `core/studio/workflow.py` | ✅ 完成 | 版本保存、恢复 |
| **工作流API** | `api/v1/studio.py` | ✅ 完成 | REST API接口 |

### 2.2 待实现功能

| 功能 | 优先级 | 说明 |
|------|-------|------|
| **测试运行** | P0 | 执行工作流并返回追踪事件 |
| **对话式创建** | P1 | 通过对话生成Agent配置 |
| **部署管理** | P1 | 一键部署为API |
| **前端可视化** | P0 | React Flow 画布 |
| **前端代码编辑器** | P0 | Monaco Editor 集成 |

---

## 实现步骤

### 阶段1: 完善后端核心功能 (1-2周)

#### 1.1 实现测试运行器

**位置**: `backend/services/studio/test_runner.py` (新建)

```python
"""
Test Runner - 测试运行器

连接工作台与 Agent Core，执行工作流并返回追踪事件
"""

from collections.abc import AsyncGenerator
from core.engine.agent import AgentEngine
from core.engine.checkpointer import Checkpointer
from core.llm.gateway import LLMGateway
from core.studio.workflow import WorkflowService
from core.studio.parser import LangGraphParser
from core.types import AgentConfig, AgentEvent
from domains.runtime.infrastructure.tools.registry import ToolRegistry
from utils.logging import get_logger

logger = get_logger(__name__)


class TestRunner:
    """测试运行器"""

    def __init__(
        self,
        workflow_service: WorkflowService,
        llm_gateway: LLMGateway,
        tool_registry: ToolRegistry,
        checkpointer: Checkpointer | None = None,
    ):
        self.workflows = workflow_service
        self.llm = llm_gateway
        self.tools = tool_registry
        self.checkpointer = checkpointer

    async def run(
        self,
        workflow_id: str,
        input_data: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        执行测试运行

        Args:
            workflow_id: 工作流ID
            input_data: 输入数据 {"message": "..."}

        Yields:
            追踪事件 (SSE格式)
        """
        # 1. 获取工作流
        workflow = await self.workflows.get(workflow_id)
        if not workflow:
            yield {
                "type": "error",
                "data": {"error": "Workflow not found"}
            }
            return

        # 2. 解析代码，转换为Agent配置
        parser = LangGraphParser()
        workflow_def = parser.parse(workflow.code)

        # 3. 构建Agent配置
        agent_config = AgentConfig(
            agent_id=f"test_{workflow_id}",
            name=workflow.name,
            system_prompt=self._extract_system_prompt(workflow_def),
            model="claude-3-5-sonnet-20241022",
            tools=self._extract_tools(workflow_def),
            max_iterations=20,
        )

        # 4. 创建临时Agent Engine
        engine = AgentEngine(
            config=agent_config,
            llm_gateway=self.llm,
            tool_registry=self.tools,
            checkpointer=self.checkpointer,
        )

        # 5. 执行并转发事件
        session_id = f"test_{workflow_id}_{int(time.time())}"
        user_message = input_data.get("message", "")

        try:
            async for event in engine.run(
                session_id=session_id,
                user_message=user_message,
            ):
                # 转换为追踪事件格式
                yield self._convert_event(event)
        except Exception as e:
            logger.exception("Test run failed")
            yield {
                "type": "error",
                "data": {"error": str(e)}
            }

    def _extract_system_prompt(self, workflow_def) -> str:
        """从工作流定义提取系统提示词"""
        # TODO: 实现提取逻辑
        return "You are a helpful AI assistant."

    def _extract_tools(self, workflow_def) -> list[str]:
        """从工作流定义提取工具列表"""
        # TODO: 实现提取逻辑
        return []

    def _convert_event(self, event: AgentEvent) -> dict[str, Any]:
        """转换Agent事件为追踪事件"""
        return {
            "type": event.type.value,
            "timestamp": time.time(),
            "data": event.data,
        }
```

#### 1.2 完善 Studio API

**位置**: `backend/api/v1/studio.py` (已有，需完善)

```python
# 在现有文件中添加测试运行端点

@router.post("/test/run")
async def test_run(
    workflow_id: str,
    request: TestRunRequest,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """测试运行工作流 (SSE)"""
    from services.studio.test_runner import TestRunner
    from api.deps import get_llm_gateway, get_tool_registry

    # 获取依赖
    llm_gateway = await get_llm_gateway()
    tool_registry = await get_tool_registry()
    workflow_service = WorkflowService()

    # 创建测试运行器
    runner = TestRunner(
        workflow_service=workflow_service,
        llm_gateway=llm_gateway,
        tool_registry=tool_registry,
    )

    # 流式返回事件
    async def event_generator():
        async for event in runner.run(workflow_id, request.input_data):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

### 阶段2: 实现前端可视化 (2-3周)

#### 2.1 安装依赖

```bash
cd frontend
npm install reactflow monaco-editor @monaco-editor/react
```

#### 2.2 创建工作流编辑器组件

**位置**: `frontend/src/pages/studio/components/workflow-editor.tsx`

```typescript
import { useCallback, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import Editor from '@monaco-editor/react';

interface WorkflowEditorProps {
  workflowId: string;
}

export function WorkflowEditor({ workflowId }: WorkflowEditorProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [code, setCode] = useState('');
  const [viewMode, setViewMode] = useState<'code' | 'visual'>('visual');

  // 代码变更时解析并更新可视化
  const handleCodeChange = useCallback(async (value: string | undefined) => {
    if (!value) return;
    setCode(value);

    // 调用后端解析API
    const response = await fetch(`/api/v1/studio/workflows/${workflowId}/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: value }),
    });
    const data = await response.json();

    if (data.nodes && data.edges) {
      setNodes(data.nodes);
      setEdges(data.edges);
    }
  }, [workflowId, setNodes, setEdges]);

  // 可视化变更时生成代码
  const handleVisualChange = useCallback(async () => {
    const response = await fetch(`/api/v1/studio/workflows/${workflowId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nodes, edges }),
    });
    const data = await response.json();

    if (data.code) {
      setCode(data.code);
    }
  }, [workflowId, nodes, edges]);

  const onConnect = useCallback(
    (params: any) => {
      setEdges((eds) => addEdge(params, eds));
      handleVisualChange();
    },
    [setEdges, handleVisualChange]
  );

  return (
    <div className="flex h-screen">
      {/* 代码编辑器 */}
      {viewMode === 'code' && (
        <div className="flex-1">
          <Editor
            height="100vh"
            defaultLanguage="python"
            value={code}
            onChange={handleCodeChange}
            theme="vs-dark"
          />
        </div>
      )}

      {/* 可视化画布 */}
      {viewMode === 'visual' && (
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
      )}

      {/* 切换按钮 */}
      <div className="absolute top-4 right-4">
        <button onClick={() => setViewMode(viewMode === 'code' ? 'visual' : 'code')}>
          {viewMode === 'code' ? '可视化' : '代码'}
        </button>
      </div>
    </div>
  );
}
```

#### 2.3 创建测试运行面板

**位置**: `frontend/src/pages/studio/components/test-panel.tsx`

```typescript
import { useState } from 'react';
import { useEventSource } from '@/hooks/use-event-source';

interface TestPanelProps {
  workflowId: string;
}

export function TestPanel({ workflowId }: TestPanelProps) {
  const [input, setInput] = useState('');
  const [events, setEvents] = useState<any[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const handleRun = async () => {
    setIsRunning(true);
    setEvents([]);

    const response = await fetch(`/api/v1/studio/test/run?workflow_id=${workflowId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input_data: { message: input } }),
    });

    // 处理SSE流
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader!.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') {
            setIsRunning(false);
            break;
          }
          try {
            const event = JSON.parse(data);
            setEvents((prev) => [...prev, event]);
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入测试消息..."
          className="w-full p-2 border rounded"
        />
        <button
          onClick={handleRun}
          disabled={isRunning}
          className="mt-2 px-4 py-2 bg-blue-500 text-white rounded"
        >
          {isRunning ? '运行中...' : '运行测试'}
        </button>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {events.map((event, i) => (
          <div key={i} className="mb-2 p-2 bg-gray-100 rounded">
            <div className="font-bold">{event.type}</div>
            <pre className="text-sm">{JSON.stringify(event.data, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 阶段3: 完善功能 (1-2周)

#### 3.1 对话式创建器

**位置**: `backend/services/studio/creator.py` (新建)

```python
"""
Agent Creator - 对话式Agent创建器

通过对话理解用户需求，生成Agent配置
"""

from core.llm.gateway import LLMGateway
from core.types import AgentConfig
from utils.logging import get_logger

logger = get_logger(__name__)


class AgentCreator:
    """对话式Agent创建器"""

    CREATOR_PROMPT = """你是一个Agent配置助手，帮助用户通过对话创建AI Agent。

用户需求: {user_input}
当前上下文: {context}

你的任务:
1. 理解用户想要创建什么类型的Agent
2. 如果信息不足，提出明确的问题
3. 信息充足时，生成完整的Agent配置

输出格式:
{{
  "action": "ask" | "preview" | "create",
  "question": "...",  // action=ask时
  "config": {{...}},   // action=preview或create时
}}
"""

    def __init__(self, llm_gateway: LLMGateway):
        self.llm = llm_gateway

    async def create(
        self,
        user_input: str,
        context: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """创建Agent配置"""
        prompt = self.CREATOR_PROMPT.format(
            user_input=user_input,
            context=context or {},
        )

        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model="claude-3-5-sonnet-20241022",
            response_format={"type": "json_object"},
        )

        return json.loads(response)
```

#### 3.2 部署管理器

**位置**: `backend/services/studio/deployer.py` (新建)

```python
"""
Deployer - 部署管理器

将工作流部署为可用的Agent实例
"""

from models.agent import Agent
from models.workflow import Workflow
from core.studio.workflow import WorkflowService
from utils.logging import get_logger

logger = get_logger(__name__)


class Deployer:
    """部署管理器"""

    def __init__(self, workflow_service: WorkflowService):
        self.workflows = workflow_service

    async def deploy(
        self,
        workflow_id: str,
        user_id: str,
        name: str,
    ) -> Agent:
        """
        部署工作流为Agent

        Args:
            workflow_id: 工作流ID
            user_id: 用户ID
            name: Agent名称

        Returns:
            创建的Agent实例
        """
        # 1. 获取工作流
        workflow = await self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError("Workflow not found")

        # 2. 解析工作流，生成Agent配置
        parser = LangGraphParser()
        workflow_def = parser.parse(workflow.code)

        # 3. 创建Agent记录
        agent = Agent(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            name=name,
            system_prompt=self._extract_system_prompt(workflow_def),
            model="claude-3-5-sonnet-20241022",
            tools=self._extract_tools(workflow_def),
            config={
                "workflow_id": str(workflow.id),
                "workflow_code": workflow.code,
            },
        )

        # 4. 保存到数据库
        async with get_async_session() as session:
            session.add(agent)
            await session.commit()
            await session.refresh(agent)

        logger.info(f"Deployed workflow {workflow_id} as agent {agent.id}")
        return agent
```

---

## 核心功能实现

### 4.1 代码解析器增强

**当前**: `core/studio/parser.py` 已实现基础解析

**需要增强**:
- 支持更多LangGraph语法
- 错误处理和提示
- 增量解析（只解析变更部分）

### 4.2 代码生成器增强

**当前**: `core/studio/codegen.py` 已实现基础生成

**需要增强**:
- 代码格式化（使用black）
- 保留用户注释
- 智能代码补全

### 4.3 双向同步机制

**实现**: 代码 ↔ 可视化的实时同步

```typescript
// 前端实现
useEffect(() => {
  // 代码变更 → 可视化
  const timer = setTimeout(() => {
    parseCode(code);
  }, 500); // 防抖
  return () => clearTimeout(timer);
}, [code]);

useEffect(() => {
  // 可视化变更 → 代码
  generateCode(nodes, edges);
}, [nodes, edges]);
```

---

## 前端实现

### 5.1 目录结构

```
frontend/src/
├── pages/
│   └── studio/
│       ├── index.tsx              # 工作台主页面
│       └── components/
│           ├── workflow-editor.tsx    # 工作流编辑器
│           ├── test-panel.tsx         # 测试面板
│           ├── code-editor.tsx        # 代码编辑器
│           └── visual-canvas.tsx      # 可视化画布
│
├── api/
│   └── studio.ts                 # 工作台API客户端
│
└── hooks/
    └── use-workflow.ts           # 工作流Hook
```

### 5.2 API客户端

**位置**: `frontend/src/api/studio.ts`

```typescript
import { client } from './client';

export interface Workflow {
  id: string;
  name: string;
  description: string;
  code: string;
  config: Record<string, any>;
}

export const studioApi = {
  // 工作流CRUD
  listWorkflows: () => client.get<Workflow[]>('/studio/workflows'),
  getWorkflow: (id: string) => client.get<Workflow>(`/studio/workflows/${id}`),
  createWorkflow: (data: { name: string; description?: string }) =>
    client.post<Workflow>('/studio/workflows', data),
  updateWorkflow: (id: string, data: Partial<Workflow>) =>
    client.put<Workflow>(`/studio/workflows/${id}`, data),
  deleteWorkflow: (id: string) =>
    client.delete(`/studio/workflows/${id}`),

  // 代码操作
  parseCode: (workflowId: string, code: string) =>
    client.post(`/studio/workflows/${workflowId}/parse`, { code }),
  generateCode: (workflowId: string, nodes: any[], edges: any[]) =>
    client.post<{ code: string }>(`/studio/workflows/${workflowId}/generate`, {
      nodes,
      edges,
    }),

  // 测试运行
  testRun: (workflowId: string, inputData: Record<string, any>) =>
    fetch(`/api/v1/studio/test/run?workflow_id=${workflowId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input_data: inputData }),
    }),

  // 版本管理
  saveVersion: (workflowId: string, message?: string) =>
    client.post(`/studio/workflows/${workflowId}/versions`, { message }),
  listVersions: (workflowId: string) =>
    client.get(`/studio/workflows/${workflowId}/versions`),
  restoreVersion: (workflowId: string, version: number) =>
    client.post(`/studio/workflows/${workflowId}/versions/${version}/restore`),
};
```

---

## 测试与调试

### 6.1 单元测试

```python
# tests/unit/test_studio_parser.py

import pytest
from core.studio.parser import LangGraphParser

def test_parse_simple_graph():
    code = """
graph = StateGraph(AgentState)
graph.add_node("node1", func1)
graph.add_node("node2", func2)
graph.add_edge("node1", "node2")
"""
    parser = LangGraphParser()
    result = parser.parse(code)

    assert len(result.nodes) == 2
    assert len(result.edges) == 1
```

### 6.2 集成测试

```python
# tests/integration/test_studio_api.py

@pytest.mark.asyncio
async def test_workflow_crud(client, auth_headers):
    # 创建
    response = await client.post(
        "/api/v1/studio/workflows",
        json={"name": "Test", "description": "Test workflow"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    workflow_id = response.json()["id"]

    # 查询
    response = await client.get(
        f"/api/v1/studio/workflows/{workflow_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
```

---

## 实施计划

### 第1周: 后端核心功能
- [ ] 实现 `TestRunner` 服务
- [ ] 完善 `studio.py` API
- [ ] 添加依赖注入

### 第2周: 前端基础
- [ ] 安装依赖 (React Flow, Monaco Editor)
- [ ] 实现工作流编辑器组件
- [ ] 实现代码编辑器集成

### 第3周: 前端高级功能
- [ ] 实现可视化画布
- [ ] 实现双向同步
- [ ] 实现测试运行面板

### 第4周: 完善与优化
- [ ] 实现对话式创建器
- [ ] 实现部署管理器
- [ ] 完善错误处理
- [ ] 添加单元测试

---

## 总结

**工作台功能应该作为现有项目的一部分实现**，而不是独立项目。

**优势**:
- ✅ 共享基础设施和代码
- ✅ 统一部署和运维
- ✅ 数据一致性
- ✅ 开发调试方便

**当前进度**:
- ✅ 后端核心模块 (workflow, parser, codegen) 已完成
- ✅ 工作流API已完成
- ⚠️ 测试运行器待实现
- ⚠️ 前端可视化待实现

**下一步**:
1. 实现 `TestRunner` 服务
2. 完善前端可视化编辑器
3. 实现双向同步机制

---

<div align="center">

**工作台负责设计 · Agent Core 负责执行**

*文档版本: v1.0.0 | 最后更新: 2026-01-14*

</div>
