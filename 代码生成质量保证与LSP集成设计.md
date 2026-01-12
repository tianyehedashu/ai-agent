# 代码生成质量保证与 LSP 集成设计

> **核心问题**: 如何保证 Agent 对话生成的代码符合架构设计，并实现运行时错误调试、检查、自动修复
> 
> **版本**: v1.0 | **更新时间**: 2026-01-12

---

## 一、问题分析

### 1.1 核心挑战

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         代码生成面临的挑战                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  用户对话输入                                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        LLM 生成代码                                  │   │
│  │                                                                      │   │
│  │  问题:                                                               │   │
│  │  ❌ 语法错误 (syntax errors)                                         │   │
│  │  ❌ 类型错误 (type mismatches)                                       │   │
│  │  ❌ 不符合架构规范 (architecture violations)                          │   │
│  │  ❌ 运行时异常 (runtime exceptions)                                  │   │
│  │  ❌ 逻辑错误 (logical bugs)                                          │   │
│  │  ❌ 安全漏洞 (security issues)                                       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  如何保证代码质量？                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 目标

| 目标 | 描述 | 优先级 |
|------|------|--------|
| **架构符合性** | 生成的代码符合 Agent 架构设计规范 | P0 |
| **类型安全** | 强类型检查，减少运行时错误 | P0 |
| **实时诊断** | LSP 集成，实时发现问题 | P1 |
| **自动修复** | 检测到错误后自动修复 | P1 |
| **沙箱验证** | 安全环境中运行验证 | P1 |

---

## 二、类型系统设计

### 2.1 强类型 vs 弱类型分析

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         类型系统对比分析                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │      Python (动态类型)          │  │    TypeScript (静态类型)         │  │
│  ├─────────────────────────────────┤  ├─────────────────────────────────┤  │
│  │                                 │  │                                 │  │
│  │  优势:                          │  │  优势:                          │  │
│  │  ✅ AI/ML 生态完善              │  │  ✅ 编译时类型检查               │  │
│  │  ✅ LangGraph/LangChain 原生    │  │  ✅ IDE 智能提示完善             │  │
│  │  ✅ 开发效率高                  │  │  ✅ 重构安全                     │  │
│  │  ✅ 学习曲线平缓                │  │  ✅ 自文档化                     │  │
│  │                                 │  │                                 │  │
│  │  劣势:                          │  │  劣势:                          │  │
│  │  ❌ 运行时类型错误              │  │  ❌ AI/ML 生态较弱               │  │
│  │  ❌ 需要额外类型检查工具        │  │  ❌ LangGraph 无原生支持         │  │
│  │                                 │  │  ❌ 需要编译步骤                 │  │
│  │                                 │  │                                 │  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     我们的选择: Python + 强类型注解                   │   │
│  │                                                                      │   │
│  │  理由:                                                               │   │
│  │  1. LangGraph 是 Python 原生，这是不可妥协的基础                     │   │
│  │  2. Python 3.10+ 类型注解已非常完善                                  │   │
│  │  3. Pydantic v2 提供运行时类型验证                                   │   │
│  │  4. mypy/pyright 提供静态类型检查                                    │   │
│  │  5. 可以达到接近 TypeScript 的类型安全                               │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Python 强类型化方案

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Python 强类型化技术栈                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  层级              工具                    作用                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  类型注解          typing / typing_extensions                               │
│                    ├─ Generic, TypeVar     泛型支持                         │
│                    ├─ Protocol             结构化类型                       │
│                    ├─ Literal              字面量类型                       │
│                    └─ TypedDict            字典类型                         │
│                                                                             │
│  运行时验证        Pydantic v2                                              │
│                    ├─ BaseModel            数据模型                         │
│                    ├─ Field                字段约束                         │
│                    ├─ validator            自定义验证                       │
│                    └─ TypeAdapter          动态验证                         │
│                                                                             │
│  静态检查          mypy / pyright                                           │
│                    ├─ 类型推断                                              │
│                    ├─ 错误检测                                              │
│                    └─ CI 集成                                               │
│                                                                             │
│  代码风格          ruff                                                     │
│                    ├─ Linting                                               │
│                    ├─ Import 排序                                           │
│                    └─ 格式化 (替代 black)                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 核心类型定义

```python
# backend/core/types.py - Agent 架构核心类型定义

from __future__ import annotations
from typing import (
    TypeVar, Generic, Protocol, Literal, TypedDict, 
    Callable, Awaitable, Any, Sequence
)
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


# ============================================================================
# 基础类型
# ============================================================================

class AgentMode(str, Enum):
    """Agent 运行模式"""
    EXECUTE = "execute"   # 完整执行权限
    ANALYZE = "analyze"   # 只读分析模式


class ToolCategory(str, Enum):
    """工具分类"""
    FILE = "file"
    CODE = "code"
    SEARCH = "search"
    DATABASE = "database"
    NETWORK = "network"


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ============================================================================
# Pydantic 模型 (运行时验证)
# ============================================================================

class Message(BaseModel):
    """消息模型"""
    model_config = ConfigDict(frozen=True)  # 不可变
    
    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """工具执行结果"""
    tool_call_id: str
    success: bool
    result: Any
    error: str | None = None
    duration_ms: int


class AgentConfig(BaseModel):
    """Agent 配置"""
    model_config = ConfigDict(strict=True)  # 严格模式
    
    name: str = Field(min_length=1, max_length=100)
    mode: AgentMode = AgentMode.EXECUTE
    model: str = "gpt-4-turbo"
    max_iterations: int = Field(default=20, ge=1, le=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    tools: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    
    # 检查点配置
    checkpoint_enabled: bool = True
    checkpoint_interval: int = Field(default=5, ge=1)
    
    # HITL 配置
    hitl_enabled: bool = True
    hitl_operations: list[str] = Field(
        default_factory=lambda: ["file_delete", "code_execute"]
    )


class AgentState(BaseModel):
    """Agent 状态 (LangGraph State)"""
    messages: list[Message] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    current_plan: list[str] | None = None
    iteration: int = 0
    status: Literal["running", "paused", "completed", "error"] = "running"


# ============================================================================
# Protocol 定义 (结构化类型)
# ============================================================================

class ToolProtocol(Protocol):
    """工具协议 - 所有工具必须实现"""
    
    @property
    def name(self) -> str:
        """工具名称"""
        ...
    
    @property
    def description(self) -> str:
        """工具描述"""
        ...
    
    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema 参数定义"""
        ...
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具"""
        ...


class CheckpointerProtocol(Protocol):
    """检查点协议"""
    
    async def save(self, session_id: str, state: AgentState) -> str:
        """保存检查点，返回 checkpoint_id"""
        ...
    
    async def load(self, checkpoint_id: str) -> AgentState:
        """加载检查点"""
        ...
    
    async def list(self, session_id: str) -> list[CheckpointMeta]:
        """列出会话的所有检查点"""
        ...


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


# ============================================================================
# 泛型类型
# ============================================================================

T = TypeVar("T")
StateT = TypeVar("StateT", bound=BaseModel)

class Result(Generic[T]):
    """结果类型 (类似 Rust Result)"""
    
    def __init__(self, value: T | None = None, error: str | None = None):
        self._value = value
        self._error = error
    
    @property
    def is_ok(self) -> bool:
        return self._error is None
    
    @property
    def is_err(self) -> bool:
        return self._error is not None
    
    def unwrap(self) -> T:
        if self._error:
            raise ValueError(self._error)
        return self._value  # type: ignore
    
    def unwrap_or(self, default: T) -> T:
        return self._value if self.is_ok else default
    
    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        return cls(value=value)
    
    @classmethod
    def err(cls, error: str) -> "Result[T]":
        return cls(error=error)


# ============================================================================
# 类型别名
# ============================================================================

ToolExecutor = Callable[..., Awaitable[ToolResult]]
NodeFunction = Callable[[AgentState], Awaitable[AgentState]]
ConditionFunction = Callable[[AgentState], str]

# JSON Schema 类型
JSONValue = str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]
JSONSchema = dict[str, Any]
```

### 2.4 类型检查配置

```toml
# pyproject.toml

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
show_error_codes = true
show_column_numbers = true

# 第三方库类型存根
[[tool.mypy.overrides]]
module = [
    "langchain.*",
    "langgraph.*",
    "litellm.*",
]
ignore_missing_imports = true


[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "strict"
reportMissingImports = true
reportMissingTypeStubs = false
reportUnusedImport = true
reportUnusedClass = true
reportUnusedFunction = true
reportUnusedVariable = true
reportDuplicateImport = true


[tool.ruff]
target-version = "py311"
line-length = 100
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "RUF",    # Ruff-specific rules
]
ignore = ["E501"]  # line too long (handled by formatter)

[tool.ruff.isort]
known-first-party = ["backend"]
```

---

## 三、LSP 集成设计

### 3.1 LSP 功能分析

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LSP 功能全景                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Language Server Protocol                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  诊断 (Diagnostics)         实时错误和警告                           │   │
│  │  ├─ 语法错误                SyntaxError, IndentationError           │   │
│  │  ├─ 类型错误                Type mismatch, Missing argument         │   │
│  │  ├─ 未使用变量              Unused variable, Unreachable code       │   │
│  │  └─ 风格问题                Line too long, Import order             │   │
│  │                                                                      │   │
│  │  补全 (Completion)          智能代码补全                             │   │
│  │  ├─ 变量/函数名             Based on scope                          │   │
│  │  ├─ 模块成员                After dot notation                      │   │
│  │  ├─ 类型提示                Type hints suggestions                  │   │
│  │  └─ 代码片段                Snippets for common patterns            │   │
│  │                                                                      │   │
│  │  导航 (Navigation)          代码导航                                 │   │
│  │  ├─ 跳转定义                Go to definition                        │   │
│  │  ├─ 查找引用                Find all references                     │   │
│  │  ├─ 符号搜索                Workspace symbol search                 │   │
│  │  └─ 文档结构                Document outline                        │   │
│  │                                                                      │   │
│  │  重构 (Refactoring)         安全重构                                 │   │
│  │  ├─ 重命名                  Rename symbol                           │   │
│  │  ├─ 提取函数                Extract function                        │   │
│  │  └─ 代码操作                Quick fixes                             │   │
│  │                                                                      │   │
│  │  悬停 (Hover)               悬停信息                                 │   │
│  │  ├─ 类型信息                Type of variable                        │   │
│  │  ├─ 文档字符串              Docstring                               │   │
│  │  └─ 函数签名                Function signature                      │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 LSP 服务器选型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Python LSP 服务器对比                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  服务器          特点                    推荐度                      │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  Pyright        微软出品，类型检查最强    ⭐⭐⭐⭐⭐                  │   │
│  │                 - 类型推断精准                                       │   │
│  │                 - 性能优秀                                           │   │
│  │                 - VSCode Pylance 底层                                │   │
│  │                                                                      │   │
│  │  pylsp          社区标准，插件丰富        ⭐⭐⭐⭐                    │   │
│  │  (python-lsp)   - 支持多种 linter                                    │   │
│  │                 - 可组合 mypy/ruff                                   │   │
│  │                 - 配置灵活                                           │   │
│  │                                                                      │   │
│  │  Jedi           轻量级，补全能力强        ⭐⭐⭐                      │   │
│  │                 - 无需配置                                           │   │
│  │                 - 类型检查较弱                                       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  我们的选择: Pyright (类型检查) + ruff (linting)                            │
│                                                                             │
│  理由:                                                                      │
│  1. Pyright 类型检查能力最强，与我们的强类型策略匹配                        │
│  2. ruff 速度极快，替代 flake8/black/isort                                 │
│  3. 两者组合覆盖所有代码质量需求                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 LSP 集成架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LSP 集成架构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          工作台前端                                   │   │
│  │                    (Monaco Editor + React)                           │   │
│  │                                                                      │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │  编辑器组件                                                  │   │   │
│  │   │  • 代码高亮                                                  │   │   │
│  │   │  • 错误波浪线                                                │   │   │
│  │   │  • 智能补全                                                  │   │   │
│  │   │  • 悬停提示                                                  │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              │ WebSocket / JSON-RPC                  │   │
│  │                              ▼                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       LSP 代理服务                                    │   │
│  │                    (FastAPI WebSocket)                               │   │
│  │                                                                      │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │  LSP Proxy                                                   │   │   │
│  │   │  • 会话管理 (多用户)                                         │   │   │
│  │   │  • 请求路由                                                  │   │   │
│  │   │  • 诊断结果缓存                                              │   │   │
│  │   │  • 权限控制                                                  │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              │ stdio / subprocess                    │   │
│  │                              ▼                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│         ┌───────────────────────┼───────────────────────┐                  │
│         ▼                       ▼                       ▼                  │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐            │
│  │   Pyright   │        │    ruff     │        │   custom    │            │
│  │   Server    │        │   (lint)    │        │  validator  │            │
│  │             │        │             │        │             │            │
│  │ 类型检查    │        │ 代码风格    │        │ 架构规范    │            │
│  └─────────────┘        └─────────────┘        └─────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 LSP 代理服务实现

```python
# backend/services/lsp_proxy.py

import asyncio
import json
from typing import Any
from pathlib import Path
from dataclasses import dataclass, field
from collections.abc import AsyncIterator

from fastapi import WebSocket
import subprocess


@dataclass
class LSPSession:
    """LSP 会话"""
    session_id: str
    project_root: Path
    process: asyncio.subprocess.Process | None = None
    request_id: int = field(default=0)
    pending_requests: dict[int, asyncio.Future[Any]] = field(default_factory=dict)


class LSPProxy:
    """LSP 代理服务"""
    
    def __init__(self):
        self.sessions: dict[str, LSPSession] = {}
    
    async def create_session(self, session_id: str, project_root: str) -> LSPSession:
        """创建 LSP 会话"""
        session = LSPSession(
            session_id=session_id,
            project_root=Path(project_root)
        )
        
        # 启动 Pyright LSP 进程
        session.process = await asyncio.create_subprocess_exec(
            "pyright-langserver", "--stdio",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_root
        )
        
        # 初始化 LSP
        await self._initialize(session)
        
        self.sessions[session_id] = session
        return session
    
    async def _initialize(self, session: LSPSession) -> dict[str, Any]:
        """初始化 LSP 连接"""
        return await self._send_request(session, "initialize", {
            "processId": None,
            "rootUri": session.project_root.as_uri(),
            "capabilities": {
                "textDocument": {
                    "synchronization": {"dynamicRegistration": True},
                    "completion": {
                        "completionItem": {"snippetSupport": True}
                    },
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "definition": {"linkSupport": True},
                    "diagnostic": {"relatedInformation": True},
                }
            }
        })
    
    async def _send_request(
        self, 
        session: LSPSession, 
        method: str, 
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """发送 LSP 请求"""
        session.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": session.request_id,
            "method": method,
            "params": params
        }
        
        content = json.dumps(request)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"
        
        assert session.process and session.process.stdin
        session.process.stdin.write(message.encode())
        await session.process.stdin.drain()
        
        # 等待响应
        response = await self._read_response(session)
        return response
    
    async def _read_response(self, session: LSPSession) -> dict[str, Any]:
        """读取 LSP 响应"""
        assert session.process and session.process.stdout
        
        # 读取 header
        headers: dict[str, str] = {}
        while True:
            line = await session.process.stdout.readline()
            line = line.decode().strip()
            if not line:
                break
            key, value = line.split(": ", 1)
            headers[key] = value
        
        # 读取 content
        content_length = int(headers["Content-Length"])
        content = await session.process.stdout.read(content_length)
        return json.loads(content)
    
    # ========================================================================
    # 核心 LSP 功能
    # ========================================================================
    
    async def get_diagnostics(
        self, 
        session_id: str, 
        file_path: str,
        content: str
    ) -> list[Diagnostic]:
        """获取代码诊断"""
        session = self.sessions[session_id]
        
        # 同步文档
        await self._send_notification(session, "textDocument/didOpen", {
            "textDocument": {
                "uri": Path(file_path).as_uri(),
                "languageId": "python",
                "version": 1,
                "text": content
            }
        })
        
        # 请求诊断
        response = await self._send_request(session, "textDocument/diagnostic", {
            "textDocument": {"uri": Path(file_path).as_uri()}
        })
        
        return [
            Diagnostic(
                line=d["range"]["start"]["line"],
                column=d["range"]["start"]["character"],
                message=d["message"],
                severity=d.get("severity", 1),
                code=d.get("code"),
                source=d.get("source", "pyright")
            )
            for d in response.get("items", [])
        ]
    
    async def get_completions(
        self,
        session_id: str,
        file_path: str,
        line: int,
        character: int
    ) -> list[CompletionItem]:
        """获取代码补全"""
        session = self.sessions[session_id]
        
        response = await self._send_request(session, "textDocument/completion", {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character}
        })
        
        items = response.get("items", []) if isinstance(response, dict) else response
        return [
            CompletionItem(
                label=item["label"],
                kind=item.get("kind"),
                detail=item.get("detail"),
                documentation=item.get("documentation"),
                insert_text=item.get("insertText", item["label"])
            )
            for item in items
        ]
    
    async def get_hover(
        self,
        session_id: str,
        file_path: str,
        line: int,
        character: int
    ) -> HoverInfo | None:
        """获取悬停信息"""
        session = self.sessions[session_id]
        
        response = await self._send_request(session, "textDocument/hover", {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character}
        })
        
        if not response:
            return None
        
        contents = response.get("contents", {})
        if isinstance(contents, dict):
            value = contents.get("value", "")
        else:
            value = str(contents)
        
        return HoverInfo(content=value)
    
    async def _send_notification(
        self,
        session: LSPSession,
        method: str,
        params: dict[str, Any]
    ) -> None:
        """发送 LSP 通知 (无响应)"""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        content = json.dumps(notification)
        message = f"Content-Length: {len(content)}\r\n\r\n{content}"
        
        assert session.process and session.process.stdin
        session.process.stdin.write(message.encode())
        await session.process.stdin.drain()


# 数据类型
@dataclass
class Diagnostic:
    line: int
    column: int
    message: str
    severity: int  # 1=Error, 2=Warning, 3=Info, 4=Hint
    code: str | None
    source: str


@dataclass
class CompletionItem:
    label: str
    kind: int | None
    detail: str | None
    documentation: str | None
    insert_text: str


@dataclass
class HoverInfo:
    content: str
```

### 3.5 ruff 集成 (Linting)

```python
# backend/services/ruff_service.py

import subprocess
import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class RuffDiagnostic:
    """Ruff 诊断结果"""
    code: str
    message: str
    filename: str
    line: int
    column: int
    end_line: int
    end_column: int
    fix: str | None = None


class RuffService:
    """Ruff 代码检查服务"""
    
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
    
    def check(self, file_path: str, content: str | None = None) -> list[RuffDiagnostic]:
        """检查代码"""
        cmd = ["ruff", "check", "--output-format=json"]
        
        if self.config_path:
            cmd.extend(["--config", self.config_path])
        
        if content:
            # 从 stdin 读取
            cmd.append("-")
            result = subprocess.run(
                cmd,
                input=content,
                capture_output=True,
                text=True
            )
        else:
            cmd.append(file_path)
            result = subprocess.run(cmd, capture_output=True, text=True)
        
        if not result.stdout:
            return []
        
        diagnostics = json.loads(result.stdout)
        return [
            RuffDiagnostic(
                code=d["code"],
                message=d["message"],
                filename=d["filename"],
                line=d["location"]["row"],
                column=d["location"]["column"],
                end_line=d["end_location"]["row"],
                end_column=d["end_location"]["column"],
                fix=d.get("fix", {}).get("content")
            )
            for d in diagnostics
        ]
    
    def format(self, content: str) -> str:
        """格式化代码"""
        result = subprocess.run(
            ["ruff", "format", "-"],
            input=content,
            capture_output=True,
            text=True
        )
        return result.stdout
    
    def fix(self, content: str) -> str:
        """自动修复代码"""
        result = subprocess.run(
            ["ruff", "check", "--fix", "-"],
            input=content,
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else content
```

---

## 四、代码生成质量保证流程

### 4.1 整体流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     代码生成质量保证流程                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  用户输入                                                                   │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. LLM 生成代码                                                     │   │
│  │     • 提供架构规范上下文                                             │   │
│  │     • 提供类型定义上下文                                             │   │
│  │     • 提供代码示例上下文                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  2. 静态检查 (不执行代码)                                            │   │
│  │     ├─ 语法检查 (ast.parse)                                          │   │
│  │     ├─ 类型检查 (pyright)                                            │   │
│  │     ├─ 风格检查 (ruff)                                               │   │
│  │     └─ 架构规范检查 (custom validator)                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│      │                                                                      │
│      ├─── 有错误 ─────────────────────────────────────────┐                │
│      │                                                    │                │
│      ▼                                                    ▼                │
│  ┌────────────────────┐                   ┌────────────────────────────┐   │
│  │  3. 沙箱执行验证   │                   │  自动修复循环               │   │
│  │     • Docker 隔离  │                   │  ├─ 错误信息 → LLM         │   │
│  │     • 超时控制     │                   │  ├─ LLM 生成修复代码       │   │
│  │     • 资源限制     │                   │  └─ 重新检查 (最多3次)     │   │
│  └────────────────────┘                   └────────────────────────────┘   │
│      │                                                    │                │
│      ├─── 执行失败 ───────────────────────────────────────┘                │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  4. 结果返回                                                         │   │
│  │     • 代码展示                                                       │   │
│  │     • 执行结果                                                       │   │
│  │     • 诊断信息                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 代码验证器实现

```python
# backend/services/code_validator.py

import ast
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from pydantic import BaseModel


class ErrorSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """验证错误"""
    line: int
    column: int
    message: str
    severity: ErrorSeverity
    code: str
    source: str  # syntax, type, lint, architecture
    fix_suggestion: str | None = None


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    formatted_code: str | None = None


class CodeValidator:
    """代码验证器"""
    
    def __init__(
        self,
        project_root: str,
        architecture_rules: dict[str, Any] | None = None
    ):
        self.project_root = Path(project_root)
        self.architecture_rules = architecture_rules or {}
        self.ruff_service = RuffService()
        self.lsp_proxy = LSPProxy()
    
    async def validate(self, code: str, filename: str = "generated.py") -> ValidationResult:
        """完整验证流程"""
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []
        
        # 1. 语法检查
        syntax_errors = self._check_syntax(code)
        if syntax_errors:
            return ValidationResult(
                is_valid=False,
                errors=syntax_errors
            )
        
        # 2. 类型检查 (Pyright via LSP)
        type_errors = await self._check_types(code, filename)
        errors.extend([e for e in type_errors if e.severity == ErrorSeverity.ERROR])
        warnings.extend([e for e in type_errors if e.severity == ErrorSeverity.WARNING])
        
        # 3. Lint 检查 (ruff)
        lint_errors = self._check_lint(code)
        errors.extend([e for e in lint_errors if e.severity == ErrorSeverity.ERROR])
        warnings.extend([e for e in lint_errors if e.severity == ErrorSeverity.WARNING])
        
        # 4. 架构规范检查
        arch_errors = self._check_architecture(code)
        errors.extend(arch_errors)
        
        # 5. 格式化代码
        formatted_code = self.ruff_service.format(code)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            formatted_code=formatted_code
        )
    
    def _check_syntax(self, code: str) -> list[ValidationError]:
        """语法检查"""
        try:
            ast.parse(code)
            return []
        except SyntaxError as e:
            return [ValidationError(
                line=e.lineno or 0,
                column=e.offset or 0,
                message=e.msg,
                severity=ErrorSeverity.ERROR,
                code="E999",
                source="syntax",
                fix_suggestion=None
            )]
    
    async def _check_types(self, code: str, filename: str) -> list[ValidationError]:
        """类型检查 (使用 Pyright)"""
        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w", 
            suffix=".py", 
            delete=False
        ) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # 运行 pyright
            result = subprocess.run(
                ["pyright", "--outputjson", temp_path],
                capture_output=True,
                text=True
            )
            
            if not result.stdout:
                return []
            
            import json
            output = json.loads(result.stdout)
            
            errors = []
            for diag in output.get("generalDiagnostics", []):
                errors.append(ValidationError(
                    line=diag["range"]["start"]["line"],
                    column=diag["range"]["start"]["character"],
                    message=diag["message"],
                    severity=ErrorSeverity.ERROR if diag["severity"] == 1 else ErrorSeverity.WARNING,
                    code=diag.get("rule", "type-error"),
                    source="type"
                ))
            
            return errors
        finally:
            Path(temp_path).unlink()
    
    def _check_lint(self, code: str) -> list[ValidationError]:
        """Lint 检查"""
        diagnostics = self.ruff_service.check("-", code)
        
        return [
            ValidationError(
                line=d.line,
                column=d.column,
                message=d.message,
                severity=ErrorSeverity.ERROR if d.code.startswith("E") else ErrorSeverity.WARNING,
                code=d.code,
                source="lint",
                fix_suggestion=d.fix
            )
            for d in diagnostics
        ]
    
    def _check_architecture(self, code: str) -> list[ValidationError]:
        """架构规范检查"""
        errors = []
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            # 检查: Agent 必须继承自 BaseAgent
            if isinstance(node, ast.ClassDef):
                if "Agent" in node.name:
                    has_base = any(
                        isinstance(base, ast.Name) and base.id == "BaseAgent"
                        for base in node.bases
                    )
                    if not has_base and node.name != "BaseAgent":
                        errors.append(ValidationError(
                            line=node.lineno,
                            column=node.col_offset,
                            message=f"Agent 类 '{node.name}' 必须继承自 BaseAgent",
                            severity=ErrorSeverity.ERROR,
                            code="ARCH001",
                            source="architecture",
                            fix_suggestion=f"class {node.name}(BaseAgent):"
                        ))
            
            # 检查: Tool 必须实现 execute 方法
            if isinstance(node, ast.ClassDef):
                if "Tool" in node.name:
                    has_execute = any(
                        isinstance(item, ast.FunctionDef) and item.name == "execute"
                        for item in node.body
                    )
                    if not has_execute:
                        errors.append(ValidationError(
                            line=node.lineno,
                            column=node.col_offset,
                            message=f"Tool 类 '{node.name}' 必须实现 execute 方法",
                            severity=ErrorSeverity.ERROR,
                            code="ARCH002",
                            source="architecture"
                        ))
            
            # 检查: 禁止使用 eval/exec
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    errors.append(ValidationError(
                        line=node.lineno,
                        column=node.col_offset,
                        message="禁止使用 eval/exec，存在安全风险",
                        severity=ErrorSeverity.ERROR,
                        code="SEC001",
                        source="architecture"
                    ))
        
        return errors
```

### 4.3 自动修复循环

```python
# backend/services/code_fixer.py

from dataclasses import dataclass
from typing import Any

from litellm import acompletion

from .code_validator import CodeValidator, ValidationResult, ValidationError


@dataclass
class FixAttempt:
    """修复尝试"""
    attempt: int
    original_code: str
    fixed_code: str
    validation_result: ValidationResult
    llm_response: str


class CodeFixer:
    """代码自动修复器"""
    
    MAX_ATTEMPTS = 3
    
    def __init__(
        self,
        validator: CodeValidator,
        model: str = "gpt-4-turbo"
    ):
        self.validator = validator
        self.model = model
    
    async def fix(
        self,
        code: str,
        errors: list[ValidationError],
        context: str = ""
    ) -> tuple[str, list[FixAttempt]]:
        """尝试自动修复代码"""
        attempts: list[FixAttempt] = []
        current_code = code
        current_errors = errors
        
        for attempt in range(self.MAX_ATTEMPTS):
            # 生成修复提示
            fix_prompt = self._build_fix_prompt(
                current_code, 
                current_errors,
                context
            )
            
            # 调用 LLM 修复
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": fix_prompt}
                ],
                temperature=0
            )
            
            fixed_code = self._extract_code(response.choices[0].message.content)
            
            # 验证修复后的代码
            result = await self.validator.validate(fixed_code)
            
            attempts.append(FixAttempt(
                attempt=attempt + 1,
                original_code=current_code,
                fixed_code=fixed_code,
                validation_result=result,
                llm_response=response.choices[0].message.content
            ))
            
            if result.is_valid:
                return fixed_code, attempts
            
            # 准备下一次修复
            current_code = fixed_code
            current_errors = result.errors
        
        # 达到最大尝试次数
        return current_code, attempts
    
    def _build_fix_prompt(
        self,
        code: str,
        errors: list[ValidationError],
        context: str
    ) -> str:
        """构建修复提示"""
        error_details = "\n".join([
            f"- 第 {e.line} 行, 第 {e.column} 列: [{e.code}] {e.message}"
            + (f"\n  建议: {e.fix_suggestion}" if e.fix_suggestion else "")
            for e in errors
        ])
        
        return f"""请修复以下代码中的错误。

## 代码
```python
{code}
```

## 错误列表
{error_details}

## 上下文
{context}

## 要求
1. 只修复列出的错误，不要做其他改动
2. 保持代码风格一致
3. 确保类型注解正确
4. 返回完整的修复后代码

请直接返回修复后的代码，用 ```python 和 ``` 包裹。
"""
    
    def _get_system_prompt(self) -> str:
        """系统提示"""
        return """你是一个专业的 Python 代码修复助手。你的任务是修复代码中的错误。

规则:
1. 只修复明确指出的错误
2. 保持代码结构和风格
3. 使用正确的类型注解
4. 遵循 PEP 8 规范
5. 不添加额外的功能或改动

返回格式:
```python
# 修复后的完整代码
```
"""
    
    def _extract_code(self, response: str) -> str:
        """从响应中提取代码"""
        import re
        
        # 匹配 ```python ... ``` 块
        pattern = r"```python\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # 如果没有代码块，返回整个响应
        return response.strip()
```

---

## 五、架构规范检查器

### 5.1 规范定义

```python
# backend/services/architecture_validator.py

import ast
from dataclasses import dataclass, field
from typing import Any, Callable
from pathlib import Path


@dataclass
class ArchitectureRule:
    """架构规则"""
    code: str
    name: str
    description: str
    check: Callable[[ast.AST, str], list["ArchViolation"]]
    severity: str = "error"  # error, warning


@dataclass
class ArchViolation:
    """架构违规"""
    rule_code: str
    line: int
    column: int
    message: str
    suggestion: str | None = None


class ArchitectureValidator:
    """架构规范验证器"""
    
    def __init__(self):
        self.rules: list[ArchitectureRule] = []
        self._register_default_rules()
    
    def _register_default_rules(self):
        """注册默认规则"""
        
        # ARCH001: Agent 继承规则
        self.rules.append(ArchitectureRule(
            code="ARCH001",
            name="agent-inheritance",
            description="Agent 类必须继承自 BaseAgent",
            check=self._check_agent_inheritance
        ))
        
        # ARCH002: Tool 实现规则
        self.rules.append(ArchitectureRule(
            code="ARCH002",
            name="tool-implementation",
            description="Tool 类必须实现 ToolProtocol",
            check=self._check_tool_implementation
        ))
        
        # ARCH003: State 类型规则
        self.rules.append(ArchitectureRule(
            code="ARCH003",
            name="state-type",
            description="Agent State 必须使用 Pydantic BaseModel",
            check=self._check_state_type
        ))
        
        # ARCH004: 异步规则
        self.rules.append(ArchitectureRule(
            code="ARCH004",
            name="async-consistency",
            description="Agent 核心方法必须是异步的",
            check=self._check_async_methods
        ))
        
        # ARCH005: 导入规则
        self.rules.append(ArchitectureRule(
            code="ARCH005",
            name="import-structure",
            description="必须使用绝对导入",
            check=self._check_imports,
            severity="warning"
        ))
        
        # SEC001: 安全规则
        self.rules.append(ArchitectureRule(
            code="SEC001",
            name="no-eval-exec",
            description="禁止使用 eval/exec",
            check=self._check_no_eval
        ))
        
        # SEC002: 硬编码密钥
        self.rules.append(ArchitectureRule(
            code="SEC002",
            name="no-hardcoded-secrets",
            description="禁止硬编码密钥",
            check=self._check_no_secrets
        ))
    
    def validate(self, code: str) -> list[ArchViolation]:
        """验证代码"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []  # 语法错误由其他检查器处理
        
        violations = []
        for rule in self.rules:
            rule_violations = rule.check(tree, code)
            violations.extend(rule_violations)
        
        return violations
    
    # ========================================================================
    # 规则检查实现
    # ========================================================================
    
    def _check_agent_inheritance(self, tree: ast.AST, code: str) -> list[ArchViolation]:
        """检查 Agent 继承"""
        violations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if "Agent" in node.name and node.name != "BaseAgent":
                    bases = [
                        base.id if isinstance(base, ast.Name) else None
                        for base in node.bases
                    ]
                    if "BaseAgent" not in bases:
                        violations.append(ArchViolation(
                            rule_code="ARCH001",
                            line=node.lineno,
                            column=node.col_offset,
                            message=f"类 '{node.name}' 包含 'Agent' 但未继承 BaseAgent",
                            suggestion=f"class {node.name}(BaseAgent):"
                        ))
        
        return violations
    
    def _check_tool_implementation(self, tree: ast.AST, code: str) -> list[ArchViolation]:
        """检查 Tool 实现"""
        violations = []
        required_methods = ["execute", "name", "description", "parameters"]
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "Tool" in node.name:
                implemented = set()
                
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        implemented.add(item.name)
                    elif isinstance(item, ast.AsyncFunctionDef):
                        implemented.add(item.name)
                    # 检查 property
                    for decorator in getattr(item, 'decorator_list', []):
                        if isinstance(decorator, ast.Name) and decorator.id == "property":
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                implemented.add(item.name)
                
                missing = set(required_methods) - implemented
                if missing:
                    violations.append(ArchViolation(
                        rule_code="ARCH002",
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Tool '{node.name}' 缺少必要方法: {', '.join(missing)}",
                        suggestion=f"实现 ToolProtocol 接口的所有方法"
                    ))
        
        return violations
    
    def _check_state_type(self, tree: ast.AST, code: str) -> list[ArchViolation]:
        """检查 State 类型"""
        violations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "State" in node.name:
                bases = [
                    base.id if isinstance(base, ast.Name) else
                    (base.attr if isinstance(base, ast.Attribute) else None)
                    for base in node.bases
                ]
                
                valid_bases = ["BaseModel", "TypedDict"]
                if not any(b in bases for b in valid_bases):
                    violations.append(ArchViolation(
                        rule_code="ARCH003",
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"State 类 '{node.name}' 必须继承 BaseModel 或 TypedDict",
                        suggestion="使用 Pydantic BaseModel 或 TypedDict 定义状态"
                    ))
        
        return violations
    
    def _check_async_methods(self, tree: ast.AST, code: str) -> list[ArchViolation]:
        """检查异步方法"""
        violations = []
        async_required = ["run", "execute", "process", "handle"]
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if "Agent" in node.name or "Tool" in node.name:
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if item.name in async_required:
                                violations.append(ArchViolation(
                                    rule_code="ARCH004",
                                    line=item.lineno,
                                    column=item.col_offset,
                                    message=f"方法 '{item.name}' 应该是异步的 (async def)",
                                    suggestion=f"async def {item.name}(...):"
                                ))
        
        return violations
    
    def _check_imports(self, tree: ast.AST, code: str) -> list[ArchViolation]:
        """检查导入"""
        violations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:  # 相对导入
                    violations.append(ArchViolation(
                        rule_code="ARCH005",
                        line=node.lineno,
                        column=node.col_offset,
                        message="建议使用绝对导入而非相对导入",
                        suggestion="使用 from backend.xxx import yyy"
                    ))
        
        return violations
    
    def _check_no_eval(self, tree: ast.AST, code: str) -> list[ArchViolation]:
        """检查 eval/exec"""
        violations = []
        dangerous = ["eval", "exec", "compile", "__import__"]
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in dangerous:
                    violations.append(ArchViolation(
                        rule_code="SEC001",
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"禁止使用 {node.func.id}()，存在安全风险",
                        suggestion="使用更安全的替代方案"
                    ))
        
        return violations
    
    def _check_no_secrets(self, tree: ast.AST, code: str) -> list[ArchViolation]:
        """检查硬编码密钥"""
        violations = []
        secret_patterns = [
            "api_key", "secret", "password", "token", "credential"
        ]
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name_lower = target.id.lower()
                        if any(p in name_lower for p in secret_patterns):
                            if isinstance(node.value, ast.Constant):
                                if isinstance(node.value.value, str) and len(node.value.value) > 5:
                                    violations.append(ArchViolation(
                                        rule_code="SEC002",
                                        line=node.lineno,
                                        column=node.col_offset,
                                        message=f"可能的硬编码密钥: {target.id}",
                                        suggestion="使用环境变量: os.getenv('...')"
                                    ))
        
        return violations
```

---

## 六、沙箱执行验证

### 6.1 Docker 沙箱

```python
# backend/services/sandbox_executor.py

import asyncio
import tempfile
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import docker
from docker.errors import ContainerError, ImageNotFound


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: str | None = None


class SandboxExecutor:
    """沙箱代码执行器"""
    
    DEFAULT_IMAGE = "python:3.11-slim"
    TIMEOUT_SECONDS = 30
    MEMORY_LIMIT = "256m"
    CPU_LIMIT = 0.5
    
    def __init__(self):
        self.client = docker.from_env()
        self._ensure_image()
    
    def _ensure_image(self):
        """确保镜像存在"""
        try:
            self.client.images.get(self.DEFAULT_IMAGE)
        except ImageNotFound:
            self.client.images.pull(self.DEFAULT_IMAGE)
    
    async def execute(
        self,
        code: str,
        requirements: list[str] | None = None,
        timeout: int | None = None
    ) -> ExecutionResult:
        """在沙箱中执行代码"""
        import time
        start_time = time.time()
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # 写入代码文件
            code_file = tmpdir_path / "main.py"
            code_file.write_text(code)
            
            # 写入 requirements (如果有)
            if requirements:
                req_file = tmpdir_path / "requirements.txt"
                req_file.write_text("\n".join(requirements))
            
            # 构建执行脚本
            script = self._build_script(requirements is not None)
            script_file = tmpdir_path / "run.sh"
            script_file.write_text(script)
            
            try:
                # 运行容器
                result = await asyncio.to_thread(
                    self._run_container,
                    tmpdir,
                    timeout or self.TIMEOUT_SECONDS
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                return ExecutionResult(
                    success=result["exit_code"] == 0,
                    stdout=result["stdout"],
                    stderr=result["stderr"],
                    exit_code=result["exit_code"],
                    duration_ms=duration_ms
                )
            
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=str(e),
                    exit_code=-1,
                    duration_ms=duration_ms,
                    error=str(e)
                )
    
    def _build_script(self, has_requirements: bool) -> str:
        """构建执行脚本"""
        script = "#!/bin/bash\nset -e\n"
        
        if has_requirements:
            script += "pip install -q -r requirements.txt\n"
        
        script += "python main.py\n"
        return script
    
    def _run_container(self, workdir: str, timeout: int) -> dict[str, Any]:
        """运行 Docker 容器"""
        container = self.client.containers.run(
            self.DEFAULT_IMAGE,
            command="bash /workspace/run.sh",
            volumes={workdir: {"bind": "/workspace", "mode": "ro"}},
            working_dir="/workspace",
            mem_limit=self.MEMORY_LIMIT,
            cpu_period=100000,
            cpu_quota=int(self.CPU_LIMIT * 100000),
            network_disabled=True,  # 禁用网络
            remove=True,
            detach=True
        )
        
        try:
            result = container.wait(timeout=timeout)
            logs = container.logs(stdout=True, stderr=True)
            
            # 分离 stdout 和 stderr
            stdout_logs = container.logs(stdout=True, stderr=False).decode()
            stderr_logs = container.logs(stdout=False, stderr=True).decode()
            
            return {
                "exit_code": result["StatusCode"],
                "stdout": stdout_logs,
                "stderr": stderr_logs
            }
        except Exception as e:
            container.kill()
            raise
        finally:
            try:
                container.remove(force=True)
            except:
                pass
    
    async def execute_with_validation(
        self,
        code: str,
        expected_output: str | None = None,
        expected_type: type | None = None
    ) -> ExecutionResult:
        """执行代码并验证结果"""
        # 包装代码以捕获结果
        wrapped_code = f"""
import json

def main():
{self._indent(code, 4)}

result = main()
print("__RESULT__:" + json.dumps(result) if result is not None else "")
"""
        
        result = await self.execute(wrapped_code)
        
        if not result.success:
            return result
        
        # 解析结果
        if "__RESULT__:" in result.stdout:
            result_line = [
                line for line in result.stdout.split("\n")
                if line.startswith("__RESULT__:")
            ]
            if result_line:
                actual_result = json.loads(result_line[0].replace("__RESULT__:", ""))
                
                # 验证输出
                if expected_output is not None and str(actual_result) != expected_output:
                    result.success = False
                    result.error = f"Expected output: {expected_output}, got: {actual_result}"
                
                # 验证类型
                if expected_type is not None and not isinstance(actual_result, expected_type):
                    result.success = False
                    result.error = f"Expected type: {expected_type}, got: {type(actual_result)}"
        
        return result
    
    def _indent(self, code: str, spaces: int) -> str:
        """缩进代码"""
        indent = " " * spaces
        return "\n".join(indent + line for line in code.split("\n"))
```

---

## 七、前端集成

### 7.1 Monaco Editor LSP 集成

```typescript
// frontend/src/components/CodeEditor/LSPEditor.tsx

import { useEffect, useRef, useState } from 'react';
import * as monaco from 'monaco-editor';
import { useWebSocket } from '@/hooks/useWebSocket';

interface LSPEditorProps {
  value: string;
  onChange: (value: string) => void;
  language?: string;
  sessionId: string;
  filePath: string;
}

export function LSPEditor({
  value,
  onChange,
  language = 'python',
  sessionId,
  filePath,
}: LSPEditorProps) {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [diagnostics, setDiagnostics] = useState<monaco.editor.IMarkerData[]>([]);
  
  // WebSocket 连接到 LSP 代理
  const { send, lastMessage } = useWebSocket(
    `/ws/lsp/${sessionId}`,
    {
      onMessage: (data) => {
        handleLSPMessage(data);
      },
    }
  );
  
  useEffect(() => {
    if (!containerRef.current) return;
    
    // 创建编辑器
    const editor = monaco.editor.create(containerRef.current, {
      value,
      language,
      theme: 'vs-dark',
      automaticLayout: true,
      minimap: { enabled: false },
      fontSize: 14,
      lineNumbers: 'on',
      renderValidationDecorations: 'on',
      quickSuggestions: true,
      suggestOnTriggerCharacters: true,
    });
    
    editorRef.current = editor;
    
    // 内容变化时
    editor.onDidChangeModelContent(() => {
      const newValue = editor.getValue();
      onChange(newValue);
      
      // 发送诊断请求
      requestDiagnostics(newValue);
    });
    
    // 补全提供者
    monaco.languages.registerCompletionItemProvider(language, {
      provideCompletionItems: async (model, position) => {
        return await requestCompletions(position);
      },
    });
    
    // 悬停提供者
    monaco.languages.registerHoverProvider(language, {
      provideHover: async (model, position) => {
        return await requestHover(position);
      },
    });
    
    return () => {
      editor.dispose();
    };
  }, []);
  
  // 请求诊断
  const requestDiagnostics = async (content: string) => {
    send({
      type: 'diagnostics',
      filePath,
      content,
    });
  };
  
  // 请求补全
  const requestCompletions = async (
    position: monaco.Position
  ): Promise<monaco.languages.CompletionList> => {
    return new Promise((resolve) => {
      const handler = (data: any) => {
        if (data.type === 'completions') {
          resolve({
            suggestions: data.items.map((item: any) => ({
              label: item.label,
              kind: mapCompletionKind(item.kind),
              insertText: item.insertText,
              detail: item.detail,
              documentation: item.documentation,
            })),
          });
        }
      };
      
      // 临时监听
      send({
        type: 'completion',
        filePath,
        line: position.lineNumber - 1,
        character: position.column - 1,
      });
      
      // 设置超时
      setTimeout(() => resolve({ suggestions: [] }), 2000);
    });
  };
  
  // 请求悬停
  const requestHover = async (
    position: monaco.Position
  ): Promise<monaco.languages.Hover | null> => {
    return new Promise((resolve) => {
      send({
        type: 'hover',
        filePath,
        line: position.lineNumber - 1,
        character: position.column - 1,
      });
      
      setTimeout(() => resolve(null), 2000);
    });
  };
  
  // 处理 LSP 消息
  const handleLSPMessage = (data: any) => {
    switch (data.type) {
      case 'diagnostics':
        const markers = data.items.map((d: any) => ({
          severity: mapSeverity(d.severity),
          startLineNumber: d.line + 1,
          startColumn: d.column + 1,
          endLineNumber: d.line + 1,
          endColumn: d.column + 10,
          message: d.message,
          source: d.source,
          code: d.code,
        }));
        
        setDiagnostics(markers);
        
        if (editorRef.current) {
          monaco.editor.setModelMarkers(
            editorRef.current.getModel()!,
            'lsp',
            markers
          );
        }
        break;
        
      // ... 其他消息类型
    }
  };
  
  return (
    <div className="relative h-full">
      <div ref={containerRef} className="h-full w-full" />
      
      {/* 诊断面板 */}
      {diagnostics.length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-700 max-h-32 overflow-y-auto">
          <div className="p-2 text-sm">
            <h4 className="text-gray-400 mb-1">问题 ({diagnostics.length})</h4>
            {diagnostics.map((d, i) => (
              <div
                key={i}
                className={`flex items-center gap-2 py-1 cursor-pointer hover:bg-gray-800 ${
                  d.severity === monaco.MarkerSeverity.Error
                    ? 'text-red-400'
                    : 'text-yellow-400'
                }`}
                onClick={() => {
                  editorRef.current?.setPosition({
                    lineNumber: d.startLineNumber,
                    column: d.startColumn,
                  });
                  editorRef.current?.focus();
                }}
              >
                <span>第 {d.startLineNumber} 行</span>
                <span>{d.message}</span>
                {d.code && <span className="text-gray-500">[{d.code}]</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// 辅助函数
function mapSeverity(severity: number): monaco.MarkerSeverity {
  switch (severity) {
    case 1: return monaco.MarkerSeverity.Error;
    case 2: return monaco.MarkerSeverity.Warning;
    case 3: return monaco.MarkerSeverity.Info;
    default: return monaco.MarkerSeverity.Hint;
  }
}

function mapCompletionKind(kind: number): monaco.languages.CompletionItemKind {
  // LSP kind to Monaco kind mapping
  const mapping: Record<number, monaco.languages.CompletionItemKind> = {
    1: monaco.languages.CompletionItemKind.Text,
    2: monaco.languages.CompletionItemKind.Method,
    3: monaco.languages.CompletionItemKind.Function,
    4: monaco.languages.CompletionItemKind.Constructor,
    5: monaco.languages.CompletionItemKind.Field,
    6: monaco.languages.CompletionItemKind.Variable,
    7: monaco.languages.CompletionItemKind.Class,
    8: monaco.languages.CompletionItemKind.Interface,
    9: monaco.languages.CompletionItemKind.Module,
    10: monaco.languages.CompletionItemKind.Property,
  };
  return mapping[kind] || monaco.languages.CompletionItemKind.Text;
}
```

---

## 八、完整验证流水线

### 8.1 集成服务

```python
# backend/services/code_quality_pipeline.py

from dataclasses import dataclass, field
from typing import Any

from .code_validator import CodeValidator, ValidationResult
from .code_fixer import CodeFixer
from .sandbox_executor import SandboxExecutor, ExecutionResult
from .architecture_validator import ArchitectureValidator


@dataclass
class QualityReport:
    """代码质量报告"""
    original_code: str
    final_code: str
    validation: ValidationResult
    execution: ExecutionResult | None
    fix_attempts: list[Any]
    is_production_ready: bool
    summary: str


class CodeQualityPipeline:
    """代码质量流水线"""
    
    def __init__(self, project_root: str):
        self.validator = CodeValidator(project_root)
        self.fixer = CodeFixer(self.validator)
        self.sandbox = SandboxExecutor()
        self.arch_validator = ArchitectureValidator()
    
    async def process(
        self,
        code: str,
        run_in_sandbox: bool = True,
        auto_fix: bool = True,
        context: str = ""
    ) -> QualityReport:
        """处理代码质量流水线"""
        
        # 1. 初始验证
        validation = await self.validator.validate(code)
        
        final_code = code
        fix_attempts = []
        
        # 2. 自动修复 (如果有错误)
        if not validation.is_valid and auto_fix:
            final_code, fix_attempts = await self.fixer.fix(
                code,
                validation.errors,
                context
            )
            
            # 重新验证
            validation = await self.validator.validate(final_code)
        
        # 3. 架构验证
        arch_violations = self.arch_validator.validate(final_code)
        for v in arch_violations:
            validation.errors.append(ValidationError(
                line=v.line,
                column=v.column,
                message=v.message,
                severity=ErrorSeverity.ERROR,
                code=v.rule_code,
                source="architecture",
                fix_suggestion=v.suggestion
            ))
        
        # 4. 沙箱执行 (如果验证通过)
        execution = None
        if validation.is_valid and run_in_sandbox:
            execution = await self.sandbox.execute(final_code)
        
        # 5. 生成报告
        is_production_ready = (
            validation.is_valid and
            (execution is None or execution.success) and
            len(arch_violations) == 0
        )
        
        summary = self._generate_summary(
            validation,
            execution,
            fix_attempts,
            is_production_ready
        )
        
        return QualityReport(
            original_code=code,
            final_code=validation.formatted_code or final_code,
            validation=validation,
            execution=execution,
            fix_attempts=fix_attempts,
            is_production_ready=is_production_ready,
            summary=summary
        )
    
    def _generate_summary(
        self,
        validation: ValidationResult,
        execution: ExecutionResult | None,
        fix_attempts: list,
        is_production_ready: bool
    ) -> str:
        """生成摘要"""
        lines = []
        
        if is_production_ready:
            lines.append("✅ 代码质量检查通过，可用于生产环境")
        else:
            lines.append("❌ 代码存在问题，需要修复")
        
        lines.append(f"\n📊 检查结果:")
        lines.append(f"  - 错误: {len(validation.errors)}")
        lines.append(f"  - 警告: {len(validation.warnings)}")
        
        if fix_attempts:
            lines.append(f"  - 自动修复尝试: {len(fix_attempts)}")
        
        if execution:
            lines.append(f"\n🔬 沙箱执行:")
            lines.append(f"  - 状态: {'成功' if execution.success else '失败'}")
            lines.append(f"  - 耗时: {execution.duration_ms}ms")
        
        if validation.errors:
            lines.append(f"\n❌ 错误详情:")
            for err in validation.errors[:5]:  # 最多显示5个
                lines.append(f"  - [{err.code}] 第{err.line}行: {err.message}")
        
        return "\n".join(lines)
```

---

## 九、配置与部署

### 9.1 依赖安装

```bash
# requirements-quality.txt

# 类型检查
pyright>=1.1.350
mypy>=1.8.0
mypy-extensions>=1.0.0

# Linting
ruff>=0.2.0

# Pydantic
pydantic>=2.5.0

# Docker (沙箱)
docker>=7.0.0

# LSP (可选)
python-lsp-server>=1.10.0
pylsp-mypy>=0.6.8
python-lsp-ruff>=2.0.0
```

### 9.2 配置文件

```yaml
# config/quality.yaml

# 类型检查配置
type_checking:
  enabled: true
  strict: true
  tool: "pyright"  # pyright | mypy

# Linting 配置
linting:
  enabled: true
  tool: "ruff"
  auto_fix: true

# 架构验证配置
architecture:
  enabled: true
  rules:
    - "ARCH001"  # Agent 继承
    - "ARCH002"  # Tool 实现
    - "ARCH003"  # State 类型
    - "ARCH004"  # 异步方法
    - "SEC001"   # 禁止 eval/exec
    - "SEC002"   # 禁止硬编码密钥

# 沙箱配置
sandbox:
  enabled: true
  timeout_seconds: 30
  memory_limit: "256m"
  cpu_limit: 0.5
  network_disabled: true

# 自动修复配置
auto_fix:
  enabled: true
  max_attempts: 3
  model: "gpt-4-turbo"

# LSP 配置
lsp:
  enabled: true
  server: "pyright"
  features:
    - diagnostics
    - completion
    - hover
    - definition
```

---

## 十、运行时状态可视化

### 10.1 设计目标

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       运行时可视化目标                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  🎯 实时看到:                                                               │
│  ├─ 当前执行到哪一步 (节点高亮)                                             │
│  ├─ 每一步的输入/输出                                                       │
│  ├─ 变量/状态的实时变化                                                     │
│  ├─ 工具调用及其结果                                                        │
│  ├─ LLM 思考过程 (streaming)                                                │
│  ├─ 错误发生的位置和上下文                                                  │
│  └─ 执行耗时统计                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 运行时追踪架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       运行时状态追踪架构                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Agent 执行引擎                               │   │
│  │                                                                      │   │
│  │   Node1 ──────► Node2 ──────► Node3 ──────► Node4                   │   │
│  │     │            │             │             │                       │   │
│  │     ▼            ▼             ▼             ▼                       │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │                    ExecutionTracer                            │   │   │
│  │  │  • 记录每一步的 state 变化                                    │   │   │
│  │  │  • 捕获工具调用和返回值                                       │   │   │
│  │  │  • 记录 LLM 输入/输出                                         │   │   │
│  │  │  • 计算每步耗时                                               │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              │ SSE / WebSocket                       │   │
│  │                              ▼                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         工作台前端                                   │   │
│  │                                                                      │   │
│  │   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │   │
│  │   │  流程图高亮    │  │  状态面板      │  │  执行日志      │        │   │
│  │   │  当前节点      │  │  变量值        │  │  实时输出      │        │   │
│  │   └────────────────┘  └────────────────┘  └────────────────┘        │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 执行追踪器实现

```python
# backend/services/execution_tracer.py

import time
import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from enum import Enum
from datetime import datetime
import json

from pydantic import BaseModel


class TraceEventType(str, Enum):
    """追踪事件类型"""
    # 流程控制
    EXECUTION_START = "execution_start"
    EXECUTION_END = "execution_end"
    NODE_ENTER = "node_enter"
    NODE_EXIT = "node_exit"
    
    # 状态变化
    STATE_UPDATE = "state_update"
    CONTEXT_UPDATE = "context_update"
    
    # LLM 交互
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_STREAM_CHUNK = "llm_stream_chunk"
    
    # 工具调用
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    
    # 检查点
    CHECKPOINT_SAVE = "checkpoint_save"
    CHECKPOINT_LOAD = "checkpoint_load"
    
    # 错误
    ERROR = "error"
    WARNING = "warning"
    
    # 调试
    DEBUG_BREAKPOINT = "debug_breakpoint"
    VARIABLE_WATCH = "variable_watch"


class TraceEvent(BaseModel):
    """追踪事件"""
    id: str
    type: TraceEventType
    timestamp: datetime
    node_id: str | None = None
    node_name: str | None = None
    data: dict[str, Any] = {}
    duration_ms: int | None = None
    
    # 状态快照
    state_snapshot: dict[str, Any] | None = None


class ExecutionTracer:
    """执行追踪器"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: list[TraceEvent] = []
        self.subscribers: list[asyncio.Queue[TraceEvent]] = []
        self._event_id = 0
        self._node_start_times: dict[str, float] = {}
    
    def _next_event_id(self) -> str:
        self._event_id += 1
        return f"{self.session_id}-{self._event_id}"
    
    async def emit(self, event: TraceEvent) -> None:
        """发送事件"""
        self.events.append(event)
        
        # 通知所有订阅者
        for queue in self.subscribers:
            await queue.put(event)
    
    def subscribe(self) -> asyncio.Queue[TraceEvent]:
        """订阅事件流"""
        queue: asyncio.Queue[TraceEvent] = asyncio.Queue()
        self.subscribers.append(queue)
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue[TraceEvent]) -> None:
        """取消订阅"""
        self.subscribers.remove(queue)
    
    # ========================================================================
    # 便捷方法
    # ========================================================================
    
    async def execution_start(self, initial_state: dict[str, Any]) -> None:
        """执行开始"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.EXECUTION_START,
            timestamp=datetime.utcnow(),
            data={"initial_input": initial_state.get("messages", [])[-1] if initial_state.get("messages") else None},
            state_snapshot=initial_state
        ))
    
    async def execution_end(self, final_state: dict[str, Any], success: bool) -> None:
        """执行结束"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.EXECUTION_END,
            timestamp=datetime.utcnow(),
            data={"success": success},
            state_snapshot=final_state
        ))
    
    async def node_enter(self, node_id: str, node_name: str, state: dict[str, Any]) -> None:
        """进入节点"""
        self._node_start_times[node_id] = time.time()
        
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.NODE_ENTER,
            timestamp=datetime.utcnow(),
            node_id=node_id,
            node_name=node_name,
            state_snapshot=state
        ))
    
    async def node_exit(self, node_id: str, node_name: str, state: dict[str, Any]) -> None:
        """退出节点"""
        duration_ms = None
        if node_id in self._node_start_times:
            duration_ms = int((time.time() - self._node_start_times[node_id]) * 1000)
            del self._node_start_times[node_id]
        
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.NODE_EXIT,
            timestamp=datetime.utcnow(),
            node_id=node_id,
            node_name=node_name,
            duration_ms=duration_ms,
            state_snapshot=state
        ))
    
    async def state_update(self, key: str, old_value: Any, new_value: Any) -> None:
        """状态更新"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.STATE_UPDATE,
            timestamp=datetime.utcnow(),
            data={
                "key": key,
                "old_value": self._safe_serialize(old_value),
                "new_value": self._safe_serialize(new_value),
            }
        ))
    
    async def llm_request(self, model: str, messages: list[dict], **kwargs) -> None:
        """LLM 请求"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.LLM_REQUEST,
            timestamp=datetime.utcnow(),
            data={
                "model": model,
                "messages": messages,
                "parameters": kwargs
            }
        ))
    
    async def llm_stream_chunk(self, chunk: str) -> None:
        """LLM 流式输出块"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.LLM_STREAM_CHUNK,
            timestamp=datetime.utcnow(),
            data={"chunk": chunk}
        ))
    
    async def llm_response(self, response: str, usage: dict | None = None) -> None:
        """LLM 响应"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.LLM_RESPONSE,
            timestamp=datetime.utcnow(),
            data={
                "response": response,
                "usage": usage
            }
        ))
    
    async def tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """工具调用"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.TOOL_CALL,
            timestamp=datetime.utcnow(),
            data={
                "tool_name": tool_name,
                "arguments": arguments
            }
        ))
    
    async def tool_result(
        self, 
        tool_name: str, 
        result: Any, 
        success: bool,
        duration_ms: int
    ) -> None:
        """工具执行结果"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.TOOL_RESULT,
            timestamp=datetime.utcnow(),
            duration_ms=duration_ms,
            data={
                "tool_name": tool_name,
                "result": self._safe_serialize(result),
                "success": success
            }
        ))
    
    async def error(self, error_type: str, message: str, traceback: str | None = None) -> None:
        """错误事件"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.ERROR,
            timestamp=datetime.utcnow(),
            data={
                "error_type": error_type,
                "message": message,
                "traceback": traceback
            }
        ))
    
    async def variable_watch(self, name: str, value: Any, location: str) -> None:
        """变量监视"""
        await self.emit(TraceEvent(
            id=self._next_event_id(),
            type=TraceEventType.VARIABLE_WATCH,
            timestamp=datetime.utcnow(),
            data={
                "name": name,
                "value": self._safe_serialize(value),
                "type": type(value).__name__,
                "location": location
            }
        ))
    
    def _safe_serialize(self, value: Any) -> Any:
        """安全序列化 (处理不可序列化的对象)"""
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)
    
    # ========================================================================
    # 查询方法
    # ========================================================================
    
    def get_timeline(self) -> list[TraceEvent]:
        """获取执行时间线"""
        return sorted(self.events, key=lambda e: e.timestamp)
    
    def get_node_history(self, node_id: str) -> list[TraceEvent]:
        """获取节点执行历史"""
        return [e for e in self.events if e.node_id == node_id]
    
    def get_state_at(self, event_id: str) -> dict[str, Any] | None:
        """获取某个事件时的状态"""
        for event in self.events:
            if event.id == event_id:
                return event.state_snapshot
        return None
    
    def get_errors(self) -> list[TraceEvent]:
        """获取所有错误"""
        return [e for e in self.events if e.type == TraceEventType.ERROR]
    
    def get_execution_stats(self) -> dict[str, Any]:
        """获取执行统计"""
        node_times: dict[str, int] = {}
        tool_times: dict[str, int] = {}
        
        for event in self.events:
            if event.type == TraceEventType.NODE_EXIT and event.duration_ms:
                node_name = event.node_name or "unknown"
                node_times[node_name] = node_times.get(node_name, 0) + event.duration_ms
            
            if event.type == TraceEventType.TOOL_RESULT and event.duration_ms:
                tool_name = event.data.get("tool_name", "unknown")
                tool_times[tool_name] = tool_times.get(tool_name, 0) + event.duration_ms
        
        return {
            "total_events": len(self.events),
            "node_execution_times": node_times,
            "tool_execution_times": tool_times,
            "error_count": len(self.get_errors())
        }
```

### 10.4 前端状态面板

```typescript
// frontend/src/components/ExecutionPanel/StatePanel.tsx

import { useState, useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Play, Pause, AlertCircle, CheckCircle, 
  Clock, Zap, Database, MessageSquare 
} from 'lucide-react';

interface TraceEvent {
  id: string;
  type: string;
  timestamp: string;
  node_id?: string;
  node_name?: string;
  data: Record<string, any>;
  duration_ms?: number;
  state_snapshot?: Record<string, any>;
}

interface ExecutionPanelProps {
  sessionId: string;
  workflowNodes: { id: string; name: string }[];
}

export function ExecutionPanel({ sessionId, workflowNodes }: ExecutionPanelProps) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [currentState, setCurrentState] = useState<Record<string, any>>({});
  const [isRunning, setIsRunning] = useState(false);
  
  // WebSocket 连接
  const { lastMessage } = useWebSocket(`/ws/execution/${sessionId}`);
  
  useEffect(() => {
    if (lastMessage) {
      const event = JSON.parse(lastMessage.data) as TraceEvent;
      setEvents(prev => [...prev, event]);
      
      // 更新当前节点
      if (event.type === 'node_enter') {
        setCurrentNode(event.node_id || null);
      } else if (event.type === 'node_exit') {
        setCurrentNode(null);
      }
      
      // 更新状态
      if (event.state_snapshot) {
        setCurrentState(event.state_snapshot);
      }
      
      // 更新运行状态
      if (event.type === 'execution_start') {
        setIsRunning(true);
      } else if (event.type === 'execution_end') {
        setIsRunning(false);
      }
    }
  }, [lastMessage]);
  
  return (
    <div className="grid grid-cols-3 gap-4 h-full">
      {/* 左侧: 流程图高亮 */}
      <Card className="p-4">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4" />
          执行流程
          {isRunning && <Badge variant="secondary">运行中</Badge>}
        </h3>
        <div className="space-y-2">
          {workflowNodes.map((node) => (
            <div
              key={node.id}
              className={`p-3 rounded-lg border transition-all ${
                currentNode === node.id
                  ? 'border-blue-500 bg-blue-500/10 animate-pulse'
                  : events.some(e => e.node_id === node.id && e.type === 'node_exit')
                  ? 'border-green-500 bg-green-500/10'
                  : 'border-gray-700 bg-gray-800'
              }`}
            >
              <div className="flex items-center justify-between">
                <span>{node.name}</span>
                {currentNode === node.id && (
                  <Badge className="bg-blue-500">执行中</Badge>
                )}
                {events.some(e => e.node_id === node.id && e.type === 'node_exit') && (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                )}
              </div>
              {/* 显示节点耗时 */}
              {events
                .filter(e => e.node_id === node.id && e.type === 'node_exit')
                .map(e => (
                  <div key={e.id} className="text-xs text-gray-400 mt-1">
                    耗时: {e.duration_ms}ms
                  </div>
                ))}
            </div>
          ))}
        </div>
      </Card>
      
      {/* 中间: 状态面板 */}
      <Card className="p-4">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <Database className="w-4 h-4" />
          当前状态
        </h3>
        <ScrollArea className="h-[400px]">
          <div className="space-y-4">
            {/* Messages */}
            {currentState.messages && (
              <div>
                <h4 className="text-sm font-medium text-gray-400 mb-2">
                  消息 ({currentState.messages.length})
                </h4>
                <div className="space-y-2">
                  {currentState.messages.slice(-3).map((msg: any, i: number) => (
                    <div
                      key={i}
                      className={`p-2 rounded text-sm ${
                        msg.role === 'user'
                          ? 'bg-blue-900/30'
                          : msg.role === 'assistant'
                          ? 'bg-green-900/30'
                          : 'bg-gray-800'
                      }`}
                    >
                      <Badge variant="outline" className="mb-1">
                        {msg.role}
                      </Badge>
                      <p className="text-gray-300 truncate">{msg.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Context */}
            {currentState.context && (
              <div>
                <h4 className="text-sm font-medium text-gray-400 mb-2">上下文</h4>
                <pre className="text-xs bg-gray-800 p-2 rounded overflow-auto">
                  {JSON.stringify(currentState.context, null, 2)}
                </pre>
              </div>
            )}
            
            {/* Iteration */}
            <div className="flex items-center gap-2">
              <span className="text-gray-400">迭代次数:</span>
              <Badge>{currentState.iteration || 0}</Badge>
            </div>
          </div>
        </ScrollArea>
      </Card>
      
      {/* 右侧: 执行日志 */}
      <Card className="p-4">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <MessageSquare className="w-4 h-4" />
          执行日志
        </h3>
        <ScrollArea className="h-[400px]">
          <div className="space-y-2">
            {events.map((event) => (
              <EventLogItem key={event.id} event={event} />
            ))}
          </div>
        </ScrollArea>
      </Card>
    </div>
  );
}

function EventLogItem({ event }: { event: TraceEvent }) {
  const getIcon = () => {
    switch (event.type) {
      case 'node_enter':
        return <Play className="w-3 h-3 text-blue-400" />;
      case 'node_exit':
        return <CheckCircle className="w-3 h-3 text-green-400" />;
      case 'tool_call':
        return <Zap className="w-3 h-3 text-yellow-400" />;
      case 'tool_result':
        return <Database className="w-3 h-3 text-purple-400" />;
      case 'llm_stream_chunk':
        return <MessageSquare className="w-3 h-3 text-cyan-400" />;
      case 'error':
        return <AlertCircle className="w-3 h-3 text-red-400" />;
      default:
        return <Clock className="w-3 h-3 text-gray-400" />;
    }
  };
  
  const getMessage = () => {
    switch (event.type) {
      case 'node_enter':
        return `进入节点: ${event.node_name}`;
      case 'node_exit':
        return `完成节点: ${event.node_name} (${event.duration_ms}ms)`;
      case 'tool_call':
        return `调用工具: ${event.data.tool_name}`;
      case 'tool_result':
        return `工具返回: ${event.data.success ? '成功' : '失败'}`;
      case 'llm_stream_chunk':
        return event.data.chunk;
      case 'error':
        return `错误: ${event.data.message}`;
      case 'state_update':
        return `状态更新: ${event.data.key}`;
      default:
        return event.type;
    }
  };
  
  return (
    <div className={`flex items-start gap-2 p-2 rounded text-sm ${
      event.type === 'error' ? 'bg-red-900/20' : 'hover:bg-gray-800'
    }`}>
      {getIcon()}
      <div className="flex-1 min-w-0">
        <p className="text-gray-300 break-words">{getMessage()}</p>
        <p className="text-xs text-gray-500">
          {new Date(event.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
```

### 10.5 实时流式输出

```python
# backend/api/routes/execution.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import AsyncIterator
import json

from backend.services.execution_tracer import ExecutionTracer, TraceEvent

router = APIRouter()


@router.websocket("/ws/execution/{session_id}")
async def execution_websocket(websocket: WebSocket, session_id: str):
    """执行状态 WebSocket"""
    await websocket.accept()
    
    # 获取或创建 tracer
    tracer = get_or_create_tracer(session_id)
    
    # 订阅事件
    queue = tracer.subscribe()
    
    try:
        while True:
            # 等待新事件
            event = await queue.get()
            
            # 发送事件到客户端
            await websocket.send_json({
                "id": event.id,
                "type": event.type.value,
                "timestamp": event.timestamp.isoformat(),
                "node_id": event.node_id,
                "node_name": event.node_name,
                "data": event.data,
                "duration_ms": event.duration_ms,
                "state_snapshot": event.state_snapshot
            })
    except WebSocketDisconnect:
        tracer.unsubscribe(queue)


@router.get("/api/v1/execution/{session_id}/timeline")
async def get_timeline(session_id: str):
    """获取执行时间线"""
    tracer = get_tracer(session_id)
    if not tracer:
        return {"events": []}
    
    return {
        "events": [
            {
                "id": e.id,
                "type": e.type.value,
                "timestamp": e.timestamp.isoformat(),
                "node_name": e.node_name,
                "duration_ms": e.duration_ms,
            }
            for e in tracer.get_timeline()
        ]
    }


@router.get("/api/v1/execution/{session_id}/stats")
async def get_stats(session_id: str):
    """获取执行统计"""
    tracer = get_tracer(session_id)
    if not tracer:
        return {}
    
    return tracer.get_execution_stats()


@router.get("/api/v1/execution/{session_id}/state/{event_id}")
async def get_state_at_event(session_id: str, event_id: str):
    """获取某个事件时的状态 (Time Travel)"""
    tracer = get_tracer(session_id)
    if not tracer:
        return None
    
    state = tracer.get_state_at(event_id)
    return {"state": state}
```

### 10.6 可视化功能总结

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    运行时可视化功能清单                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✅ 实时节点高亮                                                            │
│     • 当前执行节点蓝色高亮 + 脉冲动画                                       │
│     • 已完成节点绿色标记 + 耗时显示                                         │
│                                                                             │
│  ✅ 状态实时展示                                                            │
│     • messages 列表 (最新 3 条)                                             │
│     • context 上下文 JSON                                                   │
│     • 迭代次数                                                              │
│                                                                             │
│  ✅ 执行日志流                                                              │
│     • 节点进入/退出                                                         │
│     • 工具调用及结果                                                        │
│     • LLM 流式输出                                                          │
│     • 错误和警告                                                            │
│                                                                             │
│  ✅ 统计信息                                                                │
│     • 各节点执行耗时                                                        │
│     • 各工具调用耗时                                                        │
│     • 总事件数 / 错误数                                                     │
│                                                                             │
│  ✅ Time Travel 调试                                                        │
│     • 点击时间线查看历史状态                                                │
│     • 状态对比 (diff)                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 十一、总结

### 10.1 技术选型总结

| 组件 | 选择 | 理由 |
|------|------|------|
| **语言** | Python + 强类型注解 | LangGraph 原生 + 类型安全 |
| **类型检查** | Pyright | 最强类型检查 + VSCode 兼容 |
| **Linting** | ruff | 速度快 + 功能全 |
| **运行时验证** | Pydantic v2 | 类型验证 + 数据验证 |
| **沙箱** | Docker | 安全隔离 + 跨平台 |
| **LSP** | Pyright LSP | 与类型检查统一 |

### 10.2 质量保证流程

```
代码生成 → 语法检查 → 类型检查 → Lint 检查 → 架构检查 → 沙箱执行 → 自动修复
```

### 10.3 关键收益

| 收益 | 描述 |
|------|------|
| **类型安全** | 编译时发现 80% 的类型错误 |
| **架构一致** | 强制遵循设计规范 |
| **自动修复** | 减少人工干预 |
| **安全执行** | 沙箱隔离危险代码 |
| **实时反馈** | LSP 提供即时诊断 |

---

<div align="center">

**类型安全 · 架构一致 · 自动修复**

*文档版本: v1.0 | 更新时间: 2026-01-12*

</div>
