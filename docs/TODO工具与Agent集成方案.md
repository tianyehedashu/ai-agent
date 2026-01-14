# TODO 工具与 Agent 集成方案

> 调研日期: 2026-01-13
>
> 本文档详细分析了 TODO 工具如何与 Agent 系统深度集成，涵盖内存管理、上下文处理、检查点恢复等核心能力，并参考了 Claude Code、LangGraph 等主流开源项目的实现方案。

## 目录

1. [需求分析](#1-需求分析)
2. [业界方案调研](#2-业界方案调研)
3. [核心架构设计](#3-核心架构设计)
4. [详细设计](#4-详细设计)
5. [与现有系统集成](#5-与现有系统集成)
6. [实施计划](#6-实施计划)
7. [参考文献](#7-参考文献)

---

## 1. 需求分析

### 1.1 功能需求

| 需求类型 | 描述 | 优先级 |
|---------|------|--------|
| 任务创建 | Agent 能够自动识别用户意图并创建 TODO 任务 | P0 |
| 任务追踪 | 实时追踪任务执行进度，支持状态更新 | P0 |
| 上下文感知 | 任务关联上下文信息，支持任务间依赖 | P0 |
| 内存持久化 | 跨会话保持任务状态和执行历史 | P1 |
| 检查点恢复 | 支持从中断点恢复任务执行 | P1 |
| 任务分解 | 自动将复杂任务分解为子任务 | P2 |

### 1.2 非功能需求

- **性能**: 任务操作响应时间 < 100ms
- **可靠性**: 任务状态不丢失，支持故障恢复
- **可扩展性**: 支持自定义任务类型和工作流
- **可观测性**: 完整的任务执行日志和指标

---

## 2. 业界方案调研

### 2.1 Claude Code 实现分析

Claude Code 是 Anthropic 推出的代理式编程工具，其 TODO 工具实现具有以下特点：

#### 2.1.1 TODO 工具定义

```typescript
// Claude Code 的 todo_write 工具定义
interface TodoItem {
  id: string;           // 唯一标识符
  content: string;      // 任务描述 (最大70字符)
  status: TodoStatus;   // pending | in_progress | completed | cancelled
}

interface TodoWriteParams {
  todos: TodoItem[];    // 任务列表
  merge: boolean;       // 是否与现有任务合并
}
```

#### 2.1.2 核心设计理念

1. **轻量化设计**: 任务描述限制在 70 字符内，避免冗长
2. **状态管理**: 单一任务在任何时刻只能有一个处于 `in_progress` 状态
3. **合并策略**: 支持增量更新 (`merge=true`) 或完全替换 (`merge=false`)
4. **上下文绑定**: TODO 任务与当前会话上下文绑定

#### 2.1.3 最佳实践

```markdown
## Claude Code TODO 使用场景

✅ 适用场景:
- 复杂多步骤任务 (3+ 步骤)
- 需要仔细规划的非平凡任务
- 用户提供多个任务的情况

❌ 不适用场景:
- 单一、简单的任务
- 纯对话/信息查询请求
- 操作性任务 (linting, testing, searching)
```

### 2.2 LangGraph 实现分析

LangGraph 是基于 LangChain 的状态图框架，提供了强大的任务管理和检查点机制。

#### 2.2.1 StateGraph 核心概念

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

# 定义状态类型
class TaskState(TypedDict):
    tasks: list[dict]           # 任务列表
    current_task_id: str | None # 当前执行的任务
    context: dict               # 上下文信息
    messages: list[dict]        # 对话历史

# 创建状态图
graph = StateGraph(TaskState)

# 添加节点
graph.add_node("plan", plan_tasks)
graph.add_node("execute", execute_task)
graph.add_node("verify", verify_result)

# 配置检查点
checkpointer = SqliteSaver.from_conn_string(":memory:")
app = graph.compile(checkpointer=checkpointer)
```

#### 2.2.2 检查点机制

LangGraph 的检查点系统支持：

| 特性 | 描述 |
|-----|------|
| 自动保存 | 每个节点执行后自动保存状态 |
| 状态恢复 | 支持从任意检查点恢复执行 |
| 时间旅行 | 可以回退到历史状态重新执行 |
| 分支执行 | 支持从同一检查点创建多个执行分支 |

#### 2.2.3 Memory Saver 实现

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

# 内存存储 (开发/测试)
memory_saver = MemorySaver()

# PostgreSQL 存储 (生产环境)
postgres_saver = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost/db"
)

# 配置到图
graph = graph.compile(checkpointer=postgres_saver)
```

### 2.3 其他开源项目参考

#### 2.3.1 Confucius Code Agent (CCA)

字节跳动开源的 AI 软件工程师代理，提供了分层内存架构：

```
┌─────────────────────────────────────────────────┐
│              Confucius Code Agent               │
├─────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────────┐   │
│  │  Working Memory │  │  Persistent Notes   │   │
│  │  (短期工作记忆) │  │  (持久化笔记系统)  │   │
│  └────────┬────────┘  └──────────┬──────────┘   │
│           │                      │              │
│           ▼                      ▼              │
│  ┌────────────────────────────────────────┐     │
│  │       Unified Memory Interface          │     │
│  │       (统一记忆接口)                    │     │
│  └────────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

**核心特点**:
- 分层工作内存 (Hierarchical Working Memory)
- 持久化笔记系统支持跨会话学习
- 模块化架构，支持多种工具集成

#### 2.3.2 Git Context Controller (GCC)

受 Git 启发的上下文管理框架：

```
Context Management Operations:
├── commit()     - 保存里程碑检查点
├── branch()     - 创建执行分支
├── merge()      - 合并执行路径
├── checkout()   - 切换到历史状态
└── reflect()    - 结构化反思
```

#### 2.3.3 HiAgent

分层工作记忆管理框架，专门解决长周期任务：

```python
class HiAgent:
    def __init__(self):
        self.goal_memory = GoalMemory()      # 目标记忆
        self.task_memory = TaskMemory()      # 任务记忆
        self.action_memory = ActionMemory()  # 动作记忆

    async def decompose_goal(self, goal: str) -> list[Task]:
        """将目标分解为子任务"""
        ...

    async def execute_with_memory(self, task: Task) -> Result:
        """带记忆上下文执行任务"""
        ...
```

### 2.4 方案对比

| 特性 | Claude Code | LangGraph | CCA | HiAgent |
|-----|------------|-----------|-----|---------|
| 任务分解 | ❌ | ✅ | ✅ | ✅ |
| 检查点恢复 | ❌ | ✅ | ✅ | ✅ |
| 跨会话持久化 | ❌ | ✅ | ✅ | ✅ |
| 内存分层 | ❌ | ❌ | ✅ | ✅ |
| 多 Agent 协作 | ✅ | ✅ | ✅ | ❌ |
| 生产就绪 | ✅ | ✅ | ✅ | ❌ |

---

## 3. 核心架构设计

### 3.1 整体架构

```
┌───────────────────────────────────────────────────────────────────────┐
│                        TODO-Agent Integration System                   │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│   │   TODO Tool     │    │  Task Planner   │    │ Context Builder │  │
│   │  (任务工具层)   │    │  (任务规划器)   │    │ (上下文构建器) │  │
│   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘  │
│            │                      │                       │           │
│            └──────────────────────┼───────────────────────┘           │
│                                   │                                   │
│                                   ▼                                   │
│   ┌───────────────────────────────────────────────────────────────┐  │
│   │                    Task State Manager                          │  │
│   │                    (任务状态管理器)                            │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │  │
│   │  │ Task Store  │  │ Dependency  │  │ Progress Tracker    │    │  │
│   │  │  (任务存储) │  │   Graph     │  │   (进度追踪器)     │    │  │
│   │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘    │  │
│   └─────────┼────────────────┼────────────────────┼───────────────┘  │
│             │                │                    │                   │
│             ▼                ▼                    ▼                   │
│   ┌───────────────────────────────────────────────────────────────┐  │
│   │                    Memory Layer                                │  │
│   │                    (记忆层)                                    │  │
│   │  ┌──────────────────┐  ┌──────────────────┐                   │  │
│   │  │  Short-term      │  │  Long-term       │                   │  │
│   │  │  Memory (STM)    │  │  Memory (LTM)    │                   │  │
│   │  │  (Redis)         │  │  (PostgreSQL)    │                   │  │
│   │  └──────────────────┘  └──────────────────┘                   │  │
│   └───────────────────────────────────────────────────────────────┘  │
│             │                                                         │
│             ▼                                                         │
│   ┌───────────────────────────────────────────────────────────────┐  │
│   │                    Checkpoint System                           │  │
│   │                    (检查点系统)                                │  │
│   └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据模型设计

#### 3.2.1 任务模型

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"          # 待处理
    IN_PROGRESS = "in_progress"  # 执行中
    BLOCKED = "blocked"          # 被阻塞
    COMPLETED = "completed"      # 已完成
    CANCELLED = "cancelled"      # 已取消
    FAILED = "failed"            # 失败

class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Task(BaseModel):
    """任务模型"""
    id: str = Field(..., description="任务唯一标识")
    content: str = Field(..., max_length=200, description="任务描述")
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM

    # 上下文关联
    session_id: str = Field(..., description="所属会话")
    parent_task_id: str | None = None  # 父任务 ID
    dependencies: list[str] = Field(default_factory=list)  # 依赖任务列表

    # 执行信息
    assigned_agent: str | None = None
    checkpoint_id: str | None = None

    # 元数据
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

class TaskList(BaseModel):
    """任务列表"""
    session_id: str
    tasks: list[Task] = Field(default_factory=list)
    version: int = 1

    def get_next_task(self) -> Task | None:
        """获取下一个可执行任务"""
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                # 检查依赖是否满足
                if self._dependencies_satisfied(task):
                    return task
        return None

    def _dependencies_satisfied(self, task: Task) -> bool:
        """检查依赖是否满足"""
        for dep_id in task.dependencies:
            dep_task = next((t for t in self.tasks if t.id == dep_id), None)
            if dep_task and dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
```

#### 3.2.2 任务上下文模型

```python
class TaskContext(BaseModel):
    """任务执行上下文"""
    task_id: str

    # 对话上下文
    messages: list[dict] = Field(default_factory=list)

    # 相关记忆
    relevant_memories: list[str] = Field(default_factory=list)

    # 工具执行历史
    tool_calls: list[dict] = Field(default_factory=list)

    # 中间结果
    intermediate_results: dict = Field(default_factory=dict)

    # 错误信息
    errors: list[str] = Field(default_factory=list)

class TaskCheckpoint(BaseModel):
    """任务检查点"""
    id: str
    task_id: str
    session_id: str

    # 状态快照
    task_state: Task
    context: TaskContext

    # 检查点元数据
    step: int
    created_at: datetime
    parent_checkpoint_id: str | None = None
```

### 3.3 核心组件设计

#### 3.3.1 TODO 工具类

```python
from tools.base import BaseTool, register_tool
from core.types import ToolCategory, ToolResult

@register_tool
class TodoWriteTool(BaseTool):
    """TODO 任务管理工具"""

    name = "todo_write"
    description = """管理任务列表。用于:
    - 创建和组织复杂任务
    - 追踪多步骤任务进度
    - 规划和分解工作项

    使用时机:
    - 复杂任务 (3+ 步骤)
    - 需要规划的非平凡任务
    - 用户提供多个任务

    不要用于: 简单单步任务、纯信息查询、linting/testing 等操作性工作
    """
    category = ToolCategory.SYSTEM
    requires_confirmation = False

    async def execute(
        self,
        todos: list[dict],
        merge: bool = True,
        **kwargs
    ) -> ToolResult:
        """
        执行任务列表更新

        Args:
            todos: 任务列表，每个任务包含 id, content, status
            merge: 是否与现有任务合并
        """
        # 获取任务管理器
        task_manager = TaskStateManager()
        session_id = kwargs.get("session_id", "default")

        try:
            if merge:
                result = await task_manager.merge_tasks(session_id, todos)
            else:
                result = await task_manager.replace_tasks(session_id, todos)

            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                success=True,
                output=f"任务列表已更新: {len(todos)} 个任务",
                metadata={"tasks": result}
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                success=False,
                output="",
                error=str(e)
            )

@register_tool
class TodoReadTool(BaseTool):
    """读取当前任务列表"""

    name = "todo_read"
    description = "读取当前会话的任务列表和进度"
    category = ToolCategory.SYSTEM
    requires_confirmation = False

    async def execute(self, **kwargs) -> ToolResult:
        task_manager = TaskStateManager()
        session_id = kwargs.get("session_id", "default")

        tasks = await task_manager.get_tasks(session_id)

        # 格式化输出
        output_lines = ["## 当前任务列表\n"]
        for task in tasks:
            status_icon = {
                "pending": "⬜",
                "in_progress": "🔄",
                "completed": "✅",
                "cancelled": "❌",
                "failed": "💥"
            }.get(task.status, "❓")

            output_lines.append(f"{status_icon} [{task.id}] {task.content}")

        return ToolResult(
            tool_call_id=kwargs.get("tool_call_id", ""),
            success=True,
            output="\n".join(output_lines),
            metadata={"tasks": [t.model_dump() for t in tasks]}
        )
```

#### 3.3.2 任务状态管理器

```python
import uuid
from datetime import datetime, timezone

class TaskStateManager:
    """
    任务状态管理器

    负责任务的完整生命周期管理，包括:
    - 任务 CRUD 操作
    - 状态转换和验证
    - 依赖关系管理
    - 检查点集成
    """

    def __init__(
        self,
        short_term_store: "RedisTaskStore | None" = None,
        long_term_store: "PostgresTaskStore | None" = None,
        checkpointer: "Checkpointer | None" = None,
    ):
        self.stm = short_term_store or RedisTaskStore()
        self.ltm = long_term_store or PostgresTaskStore()
        self.checkpointer = checkpointer

    async def create_task(
        self,
        session_id: str,
        content: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: list[str] | None = None,
        parent_task_id: str | None = None,
    ) -> Task:
        """创建新任务"""
        task = Task(
            id=str(uuid.uuid4())[:8],
            content=content,
            session_id=session_id,
            priority=priority,
            dependencies=dependencies or [],
            parent_task_id=parent_task_id,
        )

        # 保存到短期存储
        await self.stm.save(task)

        # 同步到长期存储
        await self.ltm.save(task)

        return task

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        session_id: str,
    ) -> Task:
        """更新任务状态"""
        task = await self.stm.get(task_id, session_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # 状态转换验证
        self._validate_status_transition(task.status, status)

        # 更新状态
        old_status = task.status
        task.status = status
        task.updated_at = datetime.now(timezone.utc)

        if status == TaskStatus.IN_PROGRESS:
            task.started_at = datetime.now(timezone.utc)
        elif status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
            task.completed_at = datetime.now(timezone.utc)

        await self.stm.save(task)
        await self.ltm.save(task)

        # 创建检查点
        if self.checkpointer:
            await self._create_checkpoint(task, f"status: {old_status} -> {status}")

        return task

    async def merge_tasks(
        self,
        session_id: str,
        new_tasks: list[dict],
    ) -> list[Task]:
        """合并任务列表"""
        existing = await self.get_tasks(session_id)
        existing_map = {t.id: t for t in existing}

        result = []
        for task_data in new_tasks:
            task_id = task_data.get("id")

            if task_id and task_id in existing_map:
                # 更新现有任务
                task = existing_map[task_id]
                if "content" in task_data:
                    task.content = task_data["content"]
                if "status" in task_data:
                    task.status = TaskStatus(task_data["status"])
                task.updated_at = datetime.now(timezone.utc)
            else:
                # 创建新任务
                task = Task(
                    id=task_id or str(uuid.uuid4())[:8],
                    content=task_data.get("content", ""),
                    status=TaskStatus(task_data.get("status", "pending")),
                    session_id=session_id,
                )

            await self.stm.save(task)
            result.append(task)

        return result

    async def replace_tasks(
        self,
        session_id: str,
        new_tasks: list[dict],
    ) -> list[Task]:
        """替换任务列表"""
        # 清除现有任务
        await self.stm.clear(session_id)

        result = []
        for task_data in new_tasks:
            task = Task(
                id=task_data.get("id", str(uuid.uuid4())[:8]),
                content=task_data.get("content", ""),
                status=TaskStatus(task_data.get("status", "pending")),
                session_id=session_id,
            )
            await self.stm.save(task)
            result.append(task)

        return result

    async def get_tasks(self, session_id: str) -> list[Task]:
        """获取会话的所有任务"""
        return await self.stm.list_by_session(session_id)

    async def get_executable_tasks(self, session_id: str) -> list[Task]:
        """获取可执行的任务（依赖已满足）"""
        tasks = await self.get_tasks(session_id)
        task_map = {t.id: t for t in tasks}

        executable = []
        for task in tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # 检查依赖
            deps_satisfied = all(
                task_map.get(dep_id, Task(id="", content="", session_id="")).status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )

            if deps_satisfied:
                executable.append(task)

        return executable

    def _validate_status_transition(
        self,
        current: TaskStatus,
        target: TaskStatus,
    ) -> None:
        """验证状态转换是否合法"""
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED},
            TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.COMPLETED: set(),
            TaskStatus.CANCELLED: set(),
            TaskStatus.FAILED: {TaskStatus.PENDING},  # 允许重试
        }

        if target not in valid_transitions.get(current, set()):
            raise ValueError(
                f"Invalid status transition: {current} -> {target}"
            )

    async def _create_checkpoint(self, task: Task, description: str) -> str:
        """创建任务检查点"""
        if not self.checkpointer:
            return ""

        context = await self._build_task_context(task)

        checkpoint = TaskCheckpoint(
            id=str(uuid.uuid4()),
            task_id=task.id,
            session_id=task.session_id,
            task_state=task,
            context=context,
            step=0,
            created_at=datetime.now(timezone.utc),
        )

        return await self.checkpointer.save_task_checkpoint(checkpoint)
```

#### 3.3.3 任务规划器

```python
from core.llm.gateway import LLMGateway

TASK_DECOMPOSITION_PROMPT = """分析以下用户请求，将其分解为可执行的子任务。

用户请求: {user_request}

当前上下文:
{context}

请输出任务列表，格式为 JSON 数组:
[
  {
    "id": "task_1",
    "content": "具体任务描述（不超过70字）",
    "priority": "high/medium/low",
    "dependencies": []  // 依赖的其他任务 ID
  },
  ...
]

规则:
1. 每个任务描述清晰、可执行
2. 任务按依赖关系排序
3. 复杂任务拆分为 3-7 个子任务
4. 简单任务不需要拆分
5. 如果请求已经很简单，返回空数组 []
"""

class TaskPlanner:
    """
    任务规划器

    负责:
    - 分析用户请求
    - 任务分解
    - 依赖关系推断
    - 优先级评估
    """

    def __init__(
        self,
        llm: LLMGateway | None = None,
        task_manager: TaskStateManager | None = None,
    ):
        self.llm = llm or LLMGateway()
        self.task_manager = task_manager or TaskStateManager()

    async def plan_tasks(
        self,
        session_id: str,
        user_request: str,
        context: dict | None = None,
    ) -> list[Task]:
        """
        分析用户请求并创建任务计划

        Args:
            session_id: 会话 ID
            user_request: 用户请求
            context: 上下文信息

        Returns:
            创建的任务列表
        """
        # 评估任务复杂度
        complexity = await self._assess_complexity(user_request)

        if complexity < 3:
            # 简单任务，不需要分解
            return []

        # 构建提示
        prompt = TASK_DECOMPOSITION_PROMPT.format(
            user_request=user_request,
            context=self._format_context(context),
        )

        # 调用 LLM
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        # 解析响应
        task_defs = self._parse_task_definitions(response.content)

        # 创建任务
        tasks = []
        for task_def in task_defs:
            task = await self.task_manager.create_task(
                session_id=session_id,
                content=task_def["content"],
                priority=TaskPriority(task_def.get("priority", "medium")),
                dependencies=task_def.get("dependencies", []),
            )
            tasks.append(task)

        return tasks

    async def _assess_complexity(self, request: str) -> int:
        """评估请求复杂度 (1-10)"""
        # 简单启发式评估
        indicators = [
            len(request) > 100,
            "和" in request or "并且" in request,
            "首先" in request or "然后" in request,
            "多个" in request or "所有" in request,
            any(kw in request for kw in ["重构", "迁移", "集成", "实现"]),
        ]
        return sum(indicators) * 2 + 1

    def _format_context(self, context: dict | None) -> str:
        """格式化上下文"""
        if not context:
            return "无"

        lines = []
        if "current_file" in context:
            lines.append(f"当前文件: {context['current_file']}")
        if "recent_actions" in context:
            lines.append(f"最近操作: {', '.join(context['recent_actions'][:3])}")

        return "\n".join(lines) if lines else "无"

    def _parse_task_definitions(self, content: str) -> list[dict]:
        """解析任务定义"""
        import json

        # 提取 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            result = json.loads(content.strip())
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []
```

---

## 4. 详细设计

### 4.1 内存集成设计

#### 4.1.1 任务与记忆的关联

```python
class TaskMemoryIntegration:
    """任务与记忆系统的集成"""

    def __init__(
        self,
        memory_manager: "MemoryManager",
        task_manager: TaskStateManager,
    ):
        self.memory = memory_manager
        self.tasks = task_manager

    async def extract_task_memories(
        self,
        session_id: str,
        user_id: str,
    ) -> list:
        """
        从任务执行中提取记忆

        提取类型:
        - 任务完成决策
        - 失败原因和解决方案
        - 用户偏好
        """
        tasks = await self.tasks.get_tasks(session_id)

        memories = []
        for task in tasks:
            if task.status == TaskStatus.COMPLETED:
                # 记录成功完成的任务模式
                memory = await self.memory.create(
                    user_id=user_id,
                    content=f"成功完成任务: {task.content}",
                    memory_type="decision",
                    importance=6.0,
                    source_session_id=session_id,
                    metadata={"task_id": task.id, "task_type": "completed"}
                )
                memories.append(memory)

            elif task.status == TaskStatus.FAILED and task.metadata.get("error"):
                # 记录失败原因
                memory = await self.memory.create(
                    user_id=user_id,
                    content=f"任务失败: {task.content}, 原因: {task.metadata['error']}",
                    memory_type="fact",
                    importance=8.0,
                    source_session_id=session_id,
                    metadata={"task_id": task.id, "task_type": "failed"}
                )
                memories.append(memory)

        return memories

    async def get_relevant_memories_for_task(
        self,
        user_id: str,
        task: Task,
    ) -> list[str]:
        """获取与任务相关的记忆"""
        # 搜索相关记忆
        memories = await self.memory.search(
            user_id=user_id,
            query=task.content,
            limit=5,
        )

        return [m.content for m in memories]
```

#### 4.1.2 上下文构建增强

```python
class EnhancedContextManager:
    """增强的上下文管理器，支持任务上下文"""

    def __init__(self, base_manager: "ContextManager"):
        self.base = base_manager

    def build_context_with_tasks(
        self,
        messages: list,
        tasks: list[Task],
        memories: list[str] | None = None,
    ) -> list[dict]:
        """构建包含任务上下文的完整上下文"""

        # 基础上下文
        context = self.base.build_context(messages, memories)

        # 添加任务上下文
        if tasks:
            task_context = self._format_task_context(tasks)

            # 插入到系统提示中
            if context and context[0]["role"] == "system":
                context[0]["content"] += f"\n\n## 当前任务列表\n{task_context}"
            else:
                context.insert(0, {
                    "role": "system",
                    "content": f"## 当前任务列表\n{task_context}"
                })

        return context

    def _format_task_context(self, tasks: list[Task]) -> str:
        """格式化任务上下文"""
        if not tasks:
            return "暂无任务"

        lines = []
        for task in tasks:
            status_icon = {
                "pending": "⬜",
                "in_progress": "🔄",
                "completed": "✅",
                "cancelled": "❌",
                "failed": "💥",
                "blocked": "🚫",
            }.get(task.status.value, "❓")

            line = f"{status_icon} {task.content}"
            if task.status == TaskStatus.IN_PROGRESS:
                line = f"**{line}** (当前)"

            lines.append(line)

        return "\n".join(lines)
```

### 4.2 检查点集成设计

#### 4.2.1 任务检查点存储

```python
class TaskCheckpointStorage:
    """任务检查点存储"""

    def __init__(self, base_checkpointer: "Checkpointer"):
        self.checkpointer = base_checkpointer

    async def save_task_checkpoint(
        self,
        checkpoint: TaskCheckpoint,
    ) -> str:
        """保存任务检查点"""
        # 构建 AgentState
        state = AgentState(
            session_id=checkpoint.session_id,
            messages=[],
            context={
                "task": checkpoint.task_state.model_dump(),
                "task_context": checkpoint.context.model_dump(),
            },
            current_plan=[checkpoint.task_state.content],
            metadata={"checkpoint_type": "task"},
        )

        return await self.checkpointer.save(
            session_id=checkpoint.session_id,
            step=checkpoint.step,
            state=state,
            parent_id=checkpoint.parent_checkpoint_id,
        )

    async def load_task_checkpoint(
        self,
        checkpoint_id: str,
    ) -> TaskCheckpoint:
        """加载任务检查点"""
        checkpoint = await self.checkpointer.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        task_data = checkpoint.state.context.get("task", {})
        context_data = checkpoint.state.context.get("task_context", {})

        return TaskCheckpoint(
            id=checkpoint.id,
            task_id=task_data.get("id", ""),
            session_id=checkpoint.session_id,
            task_state=Task.model_validate(task_data),
            context=TaskContext.model_validate(context_data),
            step=checkpoint.step,
            created_at=checkpoint.created_at,
            parent_checkpoint_id=checkpoint.parent_id,
        )

    async def restore_task_state(
        self,
        checkpoint_id: str,
    ) -> tuple[Task, TaskContext]:
        """从检查点恢复任务状态"""
        checkpoint = await self.load_task_checkpoint(checkpoint_id)
        return checkpoint.task_state, checkpoint.context
```

### 4.3 Agent 执行循环集成

#### 4.3.1 增强的 Agent 引擎

```python
class TaskAwareAgentEngine:
    """支持任务管理的 Agent 引擎"""

    def __init__(
        self,
        base_engine: "AgentEngine",
        task_manager: TaskStateManager,
        task_planner: TaskPlanner,
    ):
        self.engine = base_engine
        self.tasks = task_manager
        self.planner = task_planner

    async def run_with_tasks(
        self,
        session_id: str,
        user_message: str,
        auto_plan: bool = True,
    ):
        """带任务管理的执行"""

        # 1. 任务规划 (可选)
        if auto_plan:
            planned_tasks = await self.planner.plan_tasks(
                session_id=session_id,
                user_request=user_message,
            )

            if planned_tasks:
                # 发送任务规划事件
                yield AgentEvent(
                    type=EventType.TEXT,
                    data={
                        "content": self._format_task_plan(planned_tasks)
                    }
                )

        # 2. 获取当前任务
        tasks = await self.tasks.get_tasks(session_id)
        current_task = next(
            (t for t in tasks if t.status == TaskStatus.IN_PROGRESS),
            None
        )

        # 3. 增强上下文
        context_manager = EnhancedContextManager(self.engine.context_manager)

        # 4. 执行引擎
        async for event in self.engine.run(session_id, user_message):
            # 任务状态同步
            if event.type == EventType.TOOL_RESULT:
                await self._sync_task_progress(session_id, event)

            yield event

        # 5. 更新任务状态
        if current_task:
            await self.tasks.update_task_status(
                current_task.id,
                TaskStatus.COMPLETED,
                session_id,
            )

    async def _sync_task_progress(
        self,
        session_id: str,
        event: AgentEvent,
    ):
        """同步任务进度"""
        # 检查是否是 todo_write 工具调用结果
        if event.data.get("tool_name") == "todo_write":
            # 任务列表已由工具更新，无需额外处理
            return

        # 对于其他工具调用，可以更新当前任务的进度
        tasks = await self.tasks.get_tasks(session_id)
        current = next(
            (t for t in tasks if t.status == TaskStatus.IN_PROGRESS),
            None
        )

        if current:
            # 更新任务元数据
            current.metadata["last_tool_call"] = event.data
            await self.tasks.stm.save(current)

    def _format_task_plan(self, tasks: list[Task]) -> str:
        """格式化任务计划"""
        lines = ["📋 **任务规划**\n"]
        for i, task in enumerate(tasks, 1):
            lines.append(f"{i}. {task.content}")
        return "\n".join(lines)
```

---

## 5. 与现有系统集成

### 5.1 API 层集成

在现有 API 路由中添加任务管理端点：

```python
# backend/api/v1/task.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/tasks", tags=["tasks"])

class TaskCreate(BaseModel):
    content: str
    priority: str = "medium"
    dependencies: list[str] = []

class TaskUpdate(BaseModel):
    content: str | None = None
    status: str | None = None
    priority: str | None = None

@router.get("/{session_id}")
async def list_tasks(
    session_id: str,
    task_manager: TaskStateManager = Depends(get_task_manager),
):
    """获取会话的任务列表"""
    tasks = await task_manager.get_tasks(session_id)
    return {"tasks": [t.model_dump() for t in tasks]}

@router.post("/{session_id}")
async def create_task(
    session_id: str,
    task: TaskCreate,
    task_manager: TaskStateManager = Depends(get_task_manager),
):
    """创建新任务"""
    created = await task_manager.create_task(
        session_id=session_id,
        content=task.content,
        priority=TaskPriority(task.priority),
        dependencies=task.dependencies,
    )
    return created.model_dump()

@router.patch("/{session_id}/{task_id}")
async def update_task(
    session_id: str,
    task_id: str,
    update: TaskUpdate,
    task_manager: TaskStateManager = Depends(get_task_manager),
):
    """更新任务"""
    if update.status:
        task = await task_manager.update_task_status(
            task_id=task_id,
            status=TaskStatus(update.status),
            session_id=session_id,
        )
    return task.model_dump()

@router.delete("/{session_id}/{task_id}")
async def delete_task(
    session_id: str,
    task_id: str,
    task_manager: TaskStateManager = Depends(get_task_manager),
):
    """删除任务"""
    await task_manager.delete_task(task_id, session_id)
    return {"success": True}
```

### 5.2 数据库 Schema

```sql
-- 任务表
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),

    content VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',

    parent_task_id UUID REFERENCES tasks(id),
    dependencies JSONB DEFAULT '[]',

    assigned_agent VARCHAR(100),
    checkpoint_id UUID,

    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'in_progress', 'blocked', 'completed', 'cancelled', 'failed')
    )
);

-- 索引
CREATE INDEX idx_tasks_session_id ON tasks(session_id);
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_parent ON tasks(parent_task_id);

-- 任务检查点表
CREATE TABLE task_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id),
    session_id UUID NOT NULL REFERENCES sessions(id),

    step INTEGER NOT NULL,
    task_state JSONB NOT NULL,
    context JSONB NOT NULL,

    parent_checkpoint_id UUID REFERENCES task_checkpoints(id),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_checkpoints_task ON task_checkpoints(task_id);
CREATE INDEX idx_task_checkpoints_session ON task_checkpoints(session_id);
```

### 5.3 前端集成

```typescript
// frontend/src/components/TaskPanel.tsx

import React from 'react';
import { useTasks } from '../hooks/useTasks';

interface TaskPanelProps {
  sessionId: string;
}

export const TaskPanel: React.FC<TaskPanelProps> = ({ sessionId }) => {
  const { tasks, updateTask, loading } = useTasks(sessionId);

  const statusIcons = {
    pending: '⬜',
    in_progress: '🔄',
    completed: '✅',
    cancelled: '❌',
    failed: '💥',
    blocked: '🚫',
  };

  if (loading) {
    return <div className="task-panel loading">加载中...</div>;
  }

  return (
    <div className="task-panel">
      <h3>📋 任务列表</h3>
      <ul className="task-list">
        {tasks.map((task) => (
          <li
            key={task.id}
            className={`task-item ${task.status}`}
          >
            <span className="task-icon">
              {statusIcons[task.status]}
            </span>
            <span className="task-content">{task.content}</span>
            {task.status === 'pending' && (
              <button
                onClick={() => updateTask(task.id, { status: 'in_progress' })}
              >
                开始
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};
```

---

## 6. 实施计划

### 6.1 阶段划分

```
Phase 1: 基础任务管理 (1-2 周)
├── 任务模型定义
├── TaskStateManager 实现
├── todo_write/todo_read 工具
└── 基础 API 端点

Phase 2: 内存集成 (1 周)
├── TaskMemoryIntegration
├── 任务记忆提取
└── 上下文增强

Phase 3: 检查点集成 (1 周)
├── TaskCheckpointStorage
├── 任务状态恢复
└── 故障恢复测试

Phase 4: 任务规划 (1-2 周)
├── TaskPlanner 实现
├── 任务分解算法
└── 依赖关系管理

Phase 5: Agent 集成 (1 周)
├── TaskAwareAgentEngine
├── 执行循环增强
└── 端到端测试

Phase 6: 前端集成 (1 周)
├── TaskPanel 组件
├── 实时状态更新
└── 用户体验优化
```

### 6.2 里程碑

| 里程碑 | 交付物 | 预计完成 |
|--------|--------|----------|
| M1 | 基础任务 CRUD 功能 | Week 2 |
| M2 | 任务与记忆集成 | Week 3 |
| M3 | 检查点和恢复功能 | Week 4 |
| M4 | 智能任务规划 | Week 6 |
| M5 | 完整系统集成 | Week 7 |
| M6 | 生产就绪 | Week 8 |

### 6.3 测试策略

```python
# tests/test_task_manager.py

import pytest
from core.task.manager import TaskStateManager, Task, TaskStatus

@pytest.fixture
async def task_manager():
    return TaskStateManager()

class TestTaskManager:

    async def test_create_task(self, task_manager):
        task = await task_manager.create_task(
            session_id="test-session",
            content="Test task",
        )
        assert task.id is not None
        assert task.status == TaskStatus.PENDING

    async def test_status_transition(self, task_manager):
        task = await task_manager.create_task(
            session_id="test-session",
            content="Test task",
        )

        # pending -> in_progress
        updated = await task_manager.update_task_status(
            task.id, TaskStatus.IN_PROGRESS, "test-session"
        )
        assert updated.status == TaskStatus.IN_PROGRESS

        # in_progress -> completed
        completed = await task_manager.update_task_status(
            task.id, TaskStatus.COMPLETED, "test-session"
        )
        assert completed.status == TaskStatus.COMPLETED

    async def test_invalid_status_transition(self, task_manager):
        task = await task_manager.create_task(
            session_id="test-session",
            content="Test task",
        )

        # pending -> completed (invalid)
        with pytest.raises(ValueError):
            await task_manager.update_task_status(
                task.id, TaskStatus.COMPLETED, "test-session"
            )

    async def test_dependency_resolution(self, task_manager):
        # 创建有依赖关系的任务
        task1 = await task_manager.create_task(
            session_id="test-session",
            content="Task 1",
        )
        task2 = await task_manager.create_task(
            session_id="test-session",
            content="Task 2",
            dependencies=[task1.id],
        )

        # task2 不应该可执行
        executable = await task_manager.get_executable_tasks("test-session")
        assert task2 not in executable

        # 完成 task1
        await task_manager.update_task_status(
            task1.id, TaskStatus.IN_PROGRESS, "test-session"
        )
        await task_manager.update_task_status(
            task1.id, TaskStatus.COMPLETED, "test-session"
        )

        # task2 现在应该可执行
        executable = await task_manager.get_executable_tasks("test-session")
        assert any(t.id == task2.id for t in executable)
```

---

## 7. 参考文献

### 7.1 论文

1. **Agentic Memory (AgeMem)** - Learning Unified Long-Term and Short-Term Memory Management for Large Language Model Agents
   - arXiv:2601.01885
   - 提出了统一的长短期记忆管理框架

2. **Git Context Controller (GCC)** - Manage the Context of LLM-based Agents like Git
   - arXiv:2508.00031
   - 受版本控制启发的上下文管理方案

3. **HiAgent** - Hierarchical Working Memory Management for LLM Agents
   - arXiv:2408.09559
   - 分层工作记忆管理框架

4. **Confucius Code Agent (CCA)** - An Open-sourced AI Software Engineer at Industrial Scale
   - arXiv:2512.10398
   - 工业级开源 AI 软件工程师

5. **AgentOrchestra** - A Hierarchical Multi-Agent Framework for General-Purpose Task Solving
   - arXiv:2506.12508
   - 多 Agent 协作框架

### 7.2 开源项目

| 项目 | 地址 | 特点 |
|------|------|------|
| LangGraph | https://github.com/langchain-ai/langgraph | 状态图框架，强大的检查点机制 |
| Claude Code | Anthropic 官方 | 简洁的 TODO 工具设计 |
| AutoGPT | https://github.com/Significant-Gravitas/AutoGPT | 自主 Agent，任务规划 |
| CrewAI | https://github.com/joaomdmoura/crewAI | 多 Agent 协作框架 |
| mem0 | https://github.com/mem0ai/mem0 | 智能记忆层 |

### 7.3 文档

- [LangGraph Checkpointing Guide](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [Claude Code Best Practices](https://docs.anthropic.com/claude-code/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

---

## 附录

### A. TODO 工具提示词模板

```markdown
## todo_write 工具

### 何时使用
1. 复杂多步骤任务（3+ 个明确步骤）
2. 需要仔细规划的非平凡任务
3. 用户明确要求创建任务列表
4. 用户提供多个任务（编号/逗号分隔）
5. 收到新指令后 - 将需求记录为 TODO
6. 完成任务后 - 标记完成并添加后续

### 何时不使用
1. 单一、简单的任务
2. 无组织价值的琐碎任务
3. 少于 3 个简单步骤即可完成的任务
4. 纯对话/信息请求
5. 操作性任务（linting、testing、searching）

### 任务状态
- pending: 未开始
- in_progress: 进行中（同时只能有一个）
- completed: 已完成
- cancelled: 已取消
```

### B. 状态机图

```
                    ┌──────────────┐
                    │   PENDING    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            │            ▼
    ┌─────────────────┐    │    ┌─────────────┐
    │   IN_PROGRESS   │    │    │  CANCELLED  │
    └────────┬────────┘    │    └─────────────┘
             │             │
    ┌────────┼────────┐    │
    │        │        │    │
    ▼        ▼        ▼    │
┌───────┐ ┌───────┐ ┌──────┴──┐
│COMPLETE│ │FAILED │ │ BLOCKED │
└───────┘ └───┬───┘ └────┬────┘
              │          │
              └──────────┘
              (retry)
```
