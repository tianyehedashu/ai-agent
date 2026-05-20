# 🧪 AI Agent 系统可测试性与 TDD 设计

> **核心目标**: 构建高可测试性架构，采用测试驱动开发确保代码质量与系统稳定性
>
> **版本**: v1.0 | **创建时间**: 2026-01-12

---

## 一、测试驱动开发 (TDD) 方法论

### 1.1 TDD 核心理念

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TDD 红-绿-重构循环                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                         ┌─────────────┐                                     │
│                         │   🔴 RED    │                                     │
│                         │  编写失败测试 │                                     │
│                         └──────┬──────┘                                     │
│                                │                                            │
│                                ▼                                            │
│      ┌─────────────┐    编写最小代码    ┌─────────────┐                     │
│      │  ♻️ REFACTOR │◀──────────────────│  🟢 GREEN  │                     │
│      │   重构优化   │    使测试通过      │  测试通过   │                     │
│      └──────┬──────┘                    └─────────────┘                     │
│             │                                                               │
│             └────────────────────────────────────────┐                      │
│                                                      │                      │
│                         下一个测试用例                ▼                      │
│                         ┌─────────────┐                                     │
│                         │   🔴 RED    │                                     │
│                         └─────────────┘                                     │
│                                                                             │
│  核心原则:                                                                  │
│  1. 先写测试，再写实现                                                      │
│  2. 只写让测试通过的最少代码                                                │
│  3. 测试通过后，重构优化代码                                                │
│  4. 保持测试始终通过                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 TDD 在 AI Agent 系统中的应用

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     AI Agent 系统 TDD 应用策略                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  模块类型              TDD 适用度        策略                               │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  纯业务逻辑            ⭐⭐⭐⭐⭐          严格 TDD                          │
│  (Token计算、状态管理)                    测试先行，100% 覆盖                │
│                                                                             │
│  数据处理              ⭐⭐⭐⭐⭐          严格 TDD                          │
│  (上下文组装、记忆检索)                   边界测试、异常测试                  │
│                                                                             │
│  工具执行              ⭐⭐⭐⭐            TDD + Mock                        │
│  (文件操作、Shell命令)                    Mock 外部依赖                      │
│                                                                             │
│  LLM 交互              ⭐⭐⭐              Mock + 集成测试                    │
│  (模型调用、响应解析)                     Mock API、真实模型测试             │
│                                                                             │
│  UI 组件               ⭐⭐⭐              组件测试 + 快照测试                │
│  (React 组件)                             Testing Library                   │
│                                                                             │
│  端到端流程            ⭐⭐                E2E 测试                          │
│  (完整对话流程)                           关键路径覆盖                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 TDD 工作流示例

```python
# 示例: TDD 开发 Token 计数器

# ============================================================================
# 步骤 1: 🔴 RED - 编写失败的测试
# ============================================================================

# tests/unit/test_token_counter.py

import pytest
from backend.utils.token import TokenCounter

class TestTokenCounter:
    """Token 计数器测试 - TDD 第一轮"""
    
    def test_count_empty_string_returns_zero(self):
        """空字符串应返回 0"""
        counter = TokenCounter()
        assert counter.count("") == 0
    
    def test_count_simple_text(self):
        """简单文本计数"""
        counter = TokenCounter()
        # "Hello world" 大约 2-3 个 token
        result = counter.count("Hello world")
        assert 2 <= result <= 3
    
    def test_count_chinese_text(self):
        """中文文本计数"""
        counter = TokenCounter()
        result = counter.count("你好世界")
        assert result > 0

# 此时运行测试会失败，因为 TokenCounter 还不存在


# ============================================================================
# 步骤 2: 🟢 GREEN - 编写最小代码使测试通过
# ============================================================================

# backend/utils/token.py

import tiktoken

class TokenCounter:
    """Token 计数器"""
    
    def __init__(self, model: str = "gpt-4"):
        self.encoding = tiktoken.encoding_for_model(model)
    
    def count(self, text: str) -> int:
        """计算文本的 token 数量"""
        if not text:
            return 0
        return len(self.encoding.encode(text))

# 运行测试 -> 全部通过 ✅


# ============================================================================
# 步骤 3: ♻️ REFACTOR - 重构优化
# ============================================================================

# backend/utils/token.py (重构版)

from functools import lru_cache
import tiktoken

class TokenCounter:
    """Token 计数器 - 支持缓存和多模型"""
    
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._encoding = None
    
    @property
    def encoding(self):
        """延迟加载编码器"""
        if self._encoding is None:
            self._encoding = tiktoken.encoding_for_model(self.model)
        return self._encoding
    
    def count(self, text: str) -> int:
        """计算文本的 token 数量"""
        if not text:
            return 0
        return len(self.encoding.encode(text))
    
    def count_messages(self, messages: list[dict]) -> int:
        """计算消息列表的 token 数量"""
        total = 0
        for msg in messages:
            total += self.count(msg.get("content", ""))
            total += 4  # 消息格式开销
        return total

# 运行测试 -> 仍然通过 ✅


# ============================================================================
# 步骤 4: 🔴 RED - 添加新测试用例
# ============================================================================

class TestTokenCounter:
    """Token 计数器测试 - TDD 第二轮"""
    
    # ... 之前的测试 ...
    
    def test_count_messages(self):
        """消息列表计数"""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        result = counter.count_messages(messages)
        assert result > 0
    
    def test_count_with_different_model(self):
        """不同模型的计数"""
        counter_gpt4 = TokenCounter(model="gpt-4")
        counter_gpt35 = TokenCounter(model="gpt-3.5-turbo")
        
        text = "Hello world"
        # 不同模型可能有不同的 token 数
        assert counter_gpt4.count(text) >= 0
        assert counter_gpt35.count(text) >= 0

# 继续 TDD 循环...
```

---

## 二、测试金字塔

### 2.1 测试层次结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              测试金字塔                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              ▲                                              │
│                             /│\         E2E 测试                            │
│                            / │ \        ──────────                          │
│                           /  │  \       • 关键用户流程                       │
│                          /   │   \      • 真实环境模拟                       │
│                         /    │    \     • 数量: 少 (~10%)                   │
│                        /─────┼─────\    • 执行: 慢 (分钟级)                  │
│                       /      │      \                                       │
│                      /       │       \                                      │
│                     /────────┼────────\   集成测试                          │
│                    /         │         \  ──────────                        │
│                   /          │          \ • 模块间交互                       │
│                  /           │           \• API 端点测试                     │
│                 /            │            \• 数量: 中 (~20%)                 │
│                /─────────────┼─────────────\• 执行: 中 (秒级)                │
│               /              │              \                               │
│              /               │               \                              │
│             /────────────────┼────────────────\  单元测试                   │
│            /                 │                 \ ──────────                 │
│           /                  │                  \• 独立函数/类测试           │
│          /                   │                   \• Mock 外部依赖           │
│         /                    │                    \• 数量: 多 (~70%)        │
│        /─────────────────────┼─────────────────────\• 执行: 快 (毫秒级)     │
│       ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔                        │
│                                                                             │
│  黄金比例: 70% 单元 : 20% 集成 : 10% E2E                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 各层测试职责

| 测试层 | 职责 | 特点 | 工具 |
|--------|------|------|------|
| **单元测试** | 测试独立函数、类、方法 | 快速、隔离、可靠 | pytest, unittest |
| **集成测试** | 测试模块间交互、API | 中等速度、部分依赖 | pytest, httpx |
| **E2E 测试** | 测试完整用户流程 | 慢速、真实环境 | Playwright, Cypress |

---

## 三、测试工具选型

### 3.1 后端测试工具栈

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          后端测试工具栈                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  核心测试框架                                                        │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  pytest              主测试框架，功能丰富，插件生态完善               │   │
│  │  pytest-asyncio      异步测试支持                                   │   │
│  │  pytest-cov          覆盖率统计                                     │   │
│  │  pytest-xdist        并行测试执行                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Mock 与 Fixture                                                    │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  pytest-mock         Mock 对象封装                                  │   │
│  │  factory-boy         测试数据工厂                                   │   │
│  │  faker               假数据生成                                     │   │
│  │  responses           HTTP 请求 Mock                                 │   │
│  │  aioresponses        异步 HTTP Mock                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  数据库测试                                                          │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  testcontainers      Docker 容器化测试环境                           │   │
│  │  pytest-postgresql   PostgreSQL 测试支持                            │   │
│  │  SQLAlchemy          ORM 测试工具                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  API 测试                                                            │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  httpx               HTTP 客户端 (支持 async)                        │   │
│  │  TestClient          FastAPI 内置测试客户端                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 前端测试工具栈

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          前端测试工具栈                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  单元/组件测试                                                       │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  Vitest              Vite 原生测试框架，快速                         │   │
│  │  @testing-library/react  React 组件测试                             │   │
│  │  @testing-library/user-event  用户交互模拟                          │   │
│  │  msw                 Mock Service Worker (API Mock)                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  E2E 测试                                                            │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  Playwright          跨浏览器 E2E 测试                               │   │
│  │  @playwright/test    Playwright 测试框架                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  辅助工具                                                            │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  @testing-library/jest-dom   DOM 断言扩展                           │   │
│  │  happy-dom           轻量级 DOM 实现                                 │   │
│  │  c8                  覆盖率统计                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 依赖配置

```toml
# pyproject.toml - 后端测试依赖

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "-ra",
]
markers = [
    "unit: 单元测试",
    "integration: 集成测试",
    "e2e: 端到端测试",
    "slow: 慢速测试",
    "llm: 需要 LLM API 的测试",
]

[tool.coverage.run]
source = ["backend"]
branch = true
omit = [
    "*/tests/*",
    "*/__pycache__/*",
    "*/migrations/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
fail_under = 80
```

```json
// package.json - 前端测试依赖

{
  "devDependencies": {
    "vitest": "^1.2.0",
    "@testing-library/react": "^14.1.0",
    "@testing-library/user-event": "^14.5.0",
    "@testing-library/jest-dom": "^6.2.0",
    "msw": "^2.0.0",
    "happy-dom": "^13.0.0",
    "@playwright/test": "^1.41.0",
    "@vitest/coverage-v8": "^1.2.0"
  },
  "scripts": {
    "test": "vitest",
    "test:coverage": "vitest --coverage",
    "test:e2e": "playwright test"
  }
}
```

---

## 四、测试目录结构

### 4.1 后端测试目录

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # 全局 fixtures
│   │
│   ├── unit/                          # 单元测试 (~70%)
│   │   ├── __init__.py
│   │   ├── conftest.py                # 单元测试 fixtures
│   │   │
│   │   ├── core/                      # Agent Core 单元测试
│   │   │   ├── test_token_counter.py
│   │   │   ├── test_context_manager.py
│   │   │   ├── test_tool_registry.py
│   │   │   ├── test_tool_executor.py
│   │   │   ├── test_memory_manager.py
│   │   │   ├── test_memory_retriever.py
│   │   │   ├── test_checkpointer.py
│   │   │   └── test_termination.py
│   │   │
│   │   ├── services/                  # 服务层单元测试
│   │   │   ├── test_code_validator.py
│   │   │   ├── test_code_fixer.py
│   │   │   ├── test_architecture_validator.py
│   │   │   └── test_lsp_proxy.py
│   │   │
│   │   ├── studio/                    # 工作台单元测试
│   │   │   ├── test_graph_parser.py
│   │   │   ├── test_graph_codegen.py
│   │   │   └── test_workflow_converter.py
│   │   │
│   │   └── utils/                     # 工具函数单元测试
│   │       ├── test_token.py
│   │       └── test_helpers.py
│   │
│   ├── integration/                   # 集成测试 (~20%)
│   │   ├── __init__.py
│   │   ├── conftest.py                # 集成测试 fixtures (DB, Redis)
│   │   │
│   │   ├── api/                       # API 端点测试
│   │   │   ├── test_chat_api.py
│   │   │   ├── test_agent_api.py
│   │   │   ├── test_session_api.py
│   │   │   ├── test_studio_api.py
│   │   │   └── test_auth_api.py
│   │   │
│   │   ├── db/                        # 数据库集成测试
│   │   │   ├── test_user_repository.py
│   │   │   ├── test_agent_repository.py
│   │   │   └── test_session_repository.py
│   │   │
│   │   └── services/                  # 服务集成测试
│   │       ├── test_agent_engine.py
│   │       ├── test_llm_gateway.py
│   │       └── test_sandbox_executor.py
│   │
│   ├── e2e/                           # 端到端测试 (~10%)
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_chat_flow.py          # 完整对话流程
│   │   ├── test_tool_execution.py     # 工具执行流程
│   │   └── test_hitl_flow.py          # Human-in-the-Loop 流程
│   │
│   ├── fixtures/                      # 测试数据
│   │   ├── agents.py
│   │   ├── messages.py
│   │   ├── workflows.py
│   │   └── sample_code/
│   │       ├── valid_agent.py
│   │       └── invalid_agent.py
│   │
│   └── mocks/                         # Mock 对象
│       ├── llm_mock.py
│       ├── tool_mock.py
│       └── db_mock.py
```

### 4.2 前端测试目录

```
frontend/
├── src/
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatMessage.tsx
│   │   │   └── ChatMessage.test.tsx   # 组件测试与组件同目录
│   │   └── workflow/
│   │       ├── WorkflowCanvas.tsx
│   │       └── WorkflowCanvas.test.tsx
│   │
│   ├── hooks/
│   │   ├── useChat.ts
│   │   └── useChat.test.ts
│   │
│   └── stores/
│       ├── chatStore.ts
│       └── chatStore.test.ts
│
├── tests/
│   ├── setup.ts                       # 测试环境配置
│   ├── mocks/
│   │   ├── handlers.ts                # MSW handlers
│   │   └── server.ts                  # MSW server
│   │
│   └── e2e/                           # Playwright E2E 测试
│       ├── chat.spec.ts
│       ├── workflow.spec.ts
│       └── auth.spec.ts
│
└── playwright.config.ts
```

---

## 五、模块测试策略

### 5.1 Agent Core 测试策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Agent Core 测试策略                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LLM Gateway                                                         │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 单元测试 + 集成测试                                        │   │
│  │                                                                      │   │
│  │  单元测试 (Mock LLM API):                                            │   │
│  │  • 请求格式验证                                                      │   │
│  │  • 响应解析正确性                                                    │   │
│  │  • 流式响应处理                                                      │   │
│  │  • 错误处理与重试                                                    │   │
│  │  • Token 计数准确性                                                  │   │
│  │                                                                      │   │
│  │  集成测试 (真实 API - 可选):                                          │   │
│  │  • 真实模型响应                                                      │   │
│  │  • 延迟与超时处理                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Context Manager                                                     │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 严格单元测试                                               │   │
│  │                                                                      │   │
│  │  测试用例:                                                           │   │
│  │  • 上下文组装顺序 (System → Memory → History → Input)                │   │
│  │  • Token 预算分配                                                    │   │
│  │  • 裁剪策略 (滑动窗口、重要性筛选)                                   │   │
│  │  • 边界条件 (空历史、超长输入)                                       │   │
│  │  • 摘要压缩                                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Tool System                                                         │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 单元测试 + 集成测试                                        │   │
│  │                                                                      │   │
│  │  单元测试:                                                           │   │
│  │  • 工具注册与发现                                                    │   │
│  │  • 参数校验 (JSON Schema)                                            │   │
│  │  • 结果格式化与截断                                                  │   │
│  │                                                                      │   │
│  │  各工具独立测试:                                                     │   │
│  │  • read_file: Mock 文件系统                                          │   │
│  │  • write_file: 临时目录验证                                          │   │
│  │  • run_shell: Mock subprocess                                        │   │
│  │  • web_search: Mock HTTP                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Agent Engine (Main Loop)                                            │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 单元测试 + 集成测试 + E2E                                  │   │
│  │                                                                      │   │
│  │  单元测试 (Mock 所有依赖):                                            │   │
│  │  • 循环控制逻辑                                                      │   │
│  │  • 终止条件检查                                                      │   │
│  │  • 事件生成                                                          │   │
│  │  • 状态转换                                                          │   │
│  │                                                                      │   │
│  │  集成测试:                                                           │   │
│  │  • Context + LLM + Tools 协作                                        │   │
│  │  • 检查点保存与恢复                                                  │   │
│  │  • HITL 中断与恢复                                                   │   │
│  │                                                                      │   │
│  │  E2E 测试:                                                           │   │
│  │  • 完整对话流程 (用户输入 → 响应)                                    │   │
│  │  • 多轮工具调用                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 工作台测试策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         工作台测试策略                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Code-First 解析器                                                   │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 严格单元测试 (纯函数，确定性)                              │   │
│  │                                                                      │   │
│  │  测试用例:                                                           │   │
│  │  • add_node 解析: graph.add_node("name", func) → NodeDefinition     │   │
│  │  • add_edge 解析: graph.add_edge("a", "b") → EdgeDefinition         │   │
│  │  • conditional_edges 解析                                            │   │
│  │  • StateGraph 识别                                                   │   │
│  │  • React Flow 格式转换                                               │   │
│  │  • 错误处理 (语法错误、不支持的模式)                                 │   │
│  │                                                                      │   │
│  │  测试数据: fixtures/sample_code/ 中的示例文件                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Code-First 生成器                                                   │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 严格单元测试                                               │   │
│  │                                                                      │   │
│  │  测试用例:                                                           │   │
│  │  • 添加节点 → 正确的代码插入位置                                     │   │
│  │  • 添加边 → 正确的代码生成                                           │   │
│  │  • 删除节点 → AST 正确移除                                           │   │
│  │  • 保留格式和注释                                                    │   │
│  │  • 解析 → 生成 → 解析 的往返一致性                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TestRunner                                                          │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 集成测试                                                   │   │
│  │                                                                      │   │
│  │  测试用例:                                                           │   │
│  │  • 工作流加载与转换                                                  │   │
│  │  • 测试执行与事件流                                                  │   │
│  │  • 追踪事件生成                                                      │   │
│  │  • 错误处理                                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 代码质量系统测试策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       代码质量系统测试策略                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CodeValidator                                                       │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 单元测试 (每种检查独立测试)                                │   │
│  │                                                                      │   │
│  │  语法检查测试:                                                       │   │
│  │  • 有效代码 → 无错误                                                 │   │
│  │  • 语法错误 → 正确定位行号                                           │   │
│  │  • 缩进错误 → 正确检测                                               │   │
│  │                                                                      │   │
│  │  类型检查测试:                                                       │   │
│  │  • 类型匹配 → 通过                                                   │   │
│  │  • 类型不匹配 → 错误                                                 │   │
│  │  • 缺少类型注解 → 警告                                               │   │
│  │                                                                      │   │
│  │  架构规范测试:                                                       │   │
│  │  • Agent 未继承 BaseAgent → ARCH001                                  │   │
│  │  • Tool 未实现 execute → ARCH002                                     │   │
│  │  • 使用 eval → SEC001                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CodeFixer                                                           │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 单元测试 + 集成测试                                        │   │
│  │                                                                      │   │
│  │  单元测试 (Mock LLM):                                                 │   │
│  │  • 修复提示构建                                                      │   │
│  │  • 代码提取                                                          │   │
│  │  • 修复循环逻辑                                                      │   │
│  │                                                                      │   │
│  │  集成测试:                                                           │   │
│  │  • 简单错误修复                                                      │   │
│  │  • 多次尝试                                                          │   │
│  │  • 不可修复代码处理                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SandboxExecutor                                                     │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │  测试类型: 集成测试 (需要 Docker)                                     │   │
│  │                                                                      │   │
│  │  测试用例:                                                           │   │
│  │  • 正常代码执行                                                      │   │
│  │  • 超时处理                                                          │   │
│  │  • 内存限制                                                          │   │
│  │  • 网络隔离验证                                                      │   │
│  │  • 错误捕获                                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、测试代码示例

### 6.1 单元测试示例

```python
# tests/unit/core/test_context_manager.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.core.agent.context import ContextManager, ContextConfig, Context
from backend.core.types import Message, MessageRole


class TestContextManager:
    """上下文管理器单元测试"""
    
    @pytest.fixture
    def config(self):
        """测试配置"""
        return ContextConfig(
            max_tokens=1000,
            system_prompt_tokens=100,
            output_tokens=200,
            recent_messages=5,
            memory_tokens=200
        )
    
    @pytest.fixture
    def mock_memory_retriever(self):
        """Mock 记忆检索器"""
        retriever = AsyncMock()
        retriever.retrieve.return_value = []
        return retriever
    
    @pytest.fixture
    def mock_token_counter(self):
        """Mock Token 计数器"""
        counter = MagicMock()
        counter.count.return_value = 10
        counter.count_messages.return_value = 50
        return counter
    
    @pytest.fixture
    def context_manager(self, config, mock_memory_retriever, mock_token_counter):
        """创建被测对象"""
        return ContextManager(
            config=config,
            memory_retriever=mock_memory_retriever,
            token_counter=mock_token_counter
        )
    
    # ========================================================================
    # 测试用例
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_build_includes_system_prompt(self, context_manager):
        """测试: 构建的上下文包含系统提示"""
        # Arrange
        system_prompt = "You are a helpful assistant."
        
        # Act
        result = await context_manager.build(
            session_id="test-session",
            user_input="Hello",
            system_prompt=system_prompt
        )
        
        # Assert
        assert result.messages[0]["role"] == "system"
        assert result.messages[0]["content"] == system_prompt
    
    @pytest.mark.asyncio
    async def test_build_includes_user_input(self, context_manager):
        """测试: 构建的上下文包含用户输入"""
        # Act
        result = await context_manager.build(
            session_id="test-session",
            user_input="Hello world",
            system_prompt="System"
        )
        
        # Assert
        user_messages = [m for m in result.messages if m["role"] == "user"]
        assert len(user_messages) >= 1
        assert user_messages[-1]["content"] == "Hello world"
    
    @pytest.mark.asyncio
    async def test_build_respects_token_budget(self, context_manager, mock_token_counter):
        """测试: Token 预算限制"""
        # Arrange
        mock_token_counter.count.return_value = 500  # 每条消息 500 tokens
        
        # Act
        result = await context_manager.build(
            session_id="test-session",
            user_input="Test",
            system_prompt="System"
        )
        
        # Assert
        # 预算 = 1000 - 200(输出) = 800
        # 系统提示固定包含，总 token 不应大幅超出预算
        assert result.total_tokens <= 1200  # 允许一定误差
    
    @pytest.mark.asyncio
    async def test_build_retrieves_memory_when_user_input_provided(
        self, 
        context_manager, 
        mock_memory_retriever
    ):
        """测试: 有用户输入时检索记忆"""
        # Act
        await context_manager.build(
            session_id="test-session",
            user_input="What did we discuss?",
            system_prompt="System"
        )
        
        # Assert
        mock_memory_retriever.retrieve.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_build_skips_memory_when_no_user_input(
        self, 
        context_manager, 
        mock_memory_retriever
    ):
        """测试: 无用户输入时跳过记忆检索"""
        # Act
        await context_manager.build(
            session_id="test-session",
            user_input=None,
            system_prompt="System"
        )
        
        # Assert
        mock_memory_retriever.retrieve.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_build_empty_history_returns_valid_context(self, context_manager):
        """测试: 空历史记录返回有效上下文"""
        # Act
        result = await context_manager.build(
            session_id="new-session",
            user_input="First message",
            system_prompt="System"
        )
        
        # Assert
        assert isinstance(result, Context)
        assert len(result.messages) >= 2  # 至少有 system 和 user
        assert result.truncated is False
```

### 6.2 LLM Mock 测试示例

```python
# tests/unit/agent/test_agent_llm_facade.py

import pytest
from unittest.mock import AsyncMock, patch
import json

from domains.agent.infrastructure.llm import AgentLlmFacade
from backend.core.types import Message, MessageRole, ToolCall


class MockLLMResponse:
    """Mock LLM 响应"""
    
    def __init__(self, content: str = "", tool_calls: list = None):
        self.choices = [
            MockChoice(content=content, tool_calls=tool_calls)
        ]
        self.usage = MockUsage(prompt_tokens=10, completion_tokens=20)


class MockChoice:
    def __init__(self, content: str, tool_calls: list = None):
        self.message = MockMessage(content=content, tool_calls=tool_calls)
        self.delta = self.message  # 用于流式


class MockMessage:
    def __init__(self, content: str, tool_calls: list = None):
        self.content = content
        self.tool_calls = tool_calls


class MockUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class TestAgentLlmFacade:
    """LLM Gateway 测试"""
    
    @pytest.fixture
    def gateway(self):
        """创建被测对象"""
        return AgentLlmFacade(
            config=LLMConfig(
                default_model="gpt-4",
                api_key="test-key"
            )
        )
    
    @pytest.mark.asyncio
    async def test_chat_returns_text_response(self, gateway):
        """测试: 返回文本响应"""
        # Arrange
        mock_response = MockLLMResponse(content="Hello, how can I help?")
        
        with patch.object(gateway, '_call_api', return_value=mock_response):
            # Act
            result = await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4"
            )
            
            # Assert
            assert result.content == "Hello, how can I help?"
            assert result.tool_calls is None
    
    @pytest.mark.asyncio
    async def test_chat_parses_tool_calls(self, gateway):
        """测试: 解析工具调用"""
        # Arrange
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = '{"path": "/tmp/test.txt"}'
        
        mock_response = MockLLMResponse(
            content="",
            tool_calls=[mock_tool_call]
        )
        
        with patch.object(gateway, '_call_api', return_value=mock_response):
            # Act
            result = await gateway.chat(
                messages=[{"role": "user", "content": "Read the file"}],
                model="gpt-4",
                tools=[{"type": "function", "function": {"name": "read_file"}}]
            )
            
            # Assert
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "read_file"
            assert result.tool_calls[0].arguments["path"] == "/tmp/test.txt"
    
    @pytest.mark.asyncio
    async def test_chat_handles_api_error(self, gateway):
        """测试: API 错误处理"""
        # Arrange
        with patch.object(gateway, '_call_api', side_effect=Exception("API Error")):
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await gateway.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gpt-4"
                )
            
            assert "API Error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_chat_with_streaming(self, gateway):
        """测试: 流式响应"""
        # Arrange
        async def mock_stream():
            chunks = [
                MockLLMResponse(content="Hello"),
                MockLLMResponse(content=" world"),
                MockLLMResponse(content="!"),
            ]
            for chunk in chunks:
                yield chunk
        
        with patch.object(gateway, '_call_api_stream', return_value=mock_stream()):
            # Act
            full_content = ""
            async for chunk in gateway.chat_stream(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4"
            ):
                full_content += chunk.content
            
            # Assert
            assert full_content == "Hello world!"
```

### 6.3 集成测试示例

```python
# tests/integration/api/test_chat_api.py

import pytest
from httpx import AsyncClient
from fastapi import status

from backend.app.main import app
from tests.fixtures.agents import create_test_agent
from tests.fixtures.users import create_test_user


class TestChatAPI:
    """Chat API 集成测试"""
    
    @pytest.fixture
    async def client(self):
        """异步测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    async def auth_headers(self, client):
        """认证头"""
        user = await create_test_user()
        response = await client.post("/api/v1/auth/login", json={
            "email": user.email,
            "password": "testpassword"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    async def test_agent(self, auth_headers):
        """测试 Agent"""
        return await create_test_agent(user_id="test-user")
    
    @pytest.mark.asyncio
    async def test_chat_returns_sse_stream(self, client, auth_headers, test_agent):
        """测试: 返回 SSE 流"""
        # Act
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-session",
                "message": "Hello",
                "agent_id": test_agent.id
            },
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream"
    
    @pytest.mark.asyncio
    async def test_chat_requires_authentication(self, client):
        """测试: 需要认证"""
        # Act
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-session",
                "message": "Hello"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_chat_validates_request_body(self, client, auth_headers):
        """测试: 请求体验证"""
        # Act
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "",  # 空字符串
                "message": "Hello"
            },
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
```

### 6.4 前端组件测试示例

```typescript
// src/components/chat/ChatMessage.test.tsx

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatMessage } from './ChatMessage';

describe('ChatMessage', () => {
  describe('用户消息', () => {
    it('应该渲染用户消息内容', () => {
      // Arrange & Act
      render(
        <ChatMessage
          role="user"
          content="Hello, how are you?"
        />
      );
      
      // Assert
      expect(screen.getByText('Hello, how are you?')).toBeInTheDocument();
    });
    
    it('应该显示用户头像', () => {
      // Arrange & Act
      render(
        <ChatMessage
          role="user"
          content="Test message"
        />
      );
      
      // Assert
      expect(screen.getByTestId('user-avatar')).toBeInTheDocument();
    });
  });
  
  describe('助手消息', () => {
    it('应该渲染助手消息内容', () => {
      // Arrange & Act
      render(
        <ChatMessage
          role="assistant"
          content="I'm doing well, thank you!"
        />
      );
      
      // Assert
      expect(screen.getByText("I'm doing well, thank you!")).toBeInTheDocument();
    });
    
    it('应该渲染 Markdown 内容', () => {
      // Arrange & Act
      render(
        <ChatMessage
          role="assistant"
          content="Here is some **bold** text"
        />
      );
      
      // Assert
      const boldElement = screen.getByText('bold');
      expect(boldElement.tagName).toBe('STRONG');
    });
    
    it('应该渲染代码块', () => {
      // Arrange & Act
      render(
        <ChatMessage
          role="assistant"
          content={'```python\nprint("hello")\n```'}
        />
      );
      
      // Assert
      expect(screen.getByText('print("hello")')).toBeInTheDocument();
    });
  });
  
  describe('工具调用', () => {
    it('应该渲染工具调用信息', () => {
      // Arrange & Act
      render(
        <ChatMessage
          role="assistant"
          content=""
          toolCalls={[
            {
              id: 'call_123',
              name: 'read_file',
              arguments: { path: '/tmp/test.txt' }
            }
          ]}
        />
      );
      
      // Assert
      expect(screen.getByText('read_file')).toBeInTheDocument();
      expect(screen.getByText('/tmp/test.txt')).toBeInTheDocument();
    });
  });
  
  describe('加载状态', () => {
    it('应该显示加载指示器', () => {
      // Arrange & Act
      render(
        <ChatMessage
          role="assistant"
          content=""
          isLoading={true}
        />
      );
      
      // Assert
      expect(screen.getByTestId('loading-indicator')).toBeInTheDocument();
    });
  });
});
```

### 6.5 E2E 测试示例

```typescript
// tests/e2e/chat.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Chat Flow', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'password123');
    await page.click('[data-testid="login-button"]');
    
    // 等待登录完成
    await page.waitForURL('/chat');
  });
  
  test('用户可以发送消息并收到响应', async ({ page }) => {
    // Arrange
    await page.goto('/chat');
    
    // Act
    await page.fill('[data-testid="chat-input"]', 'Hello, what can you do?');
    await page.click('[data-testid="send-button"]');
    
    // Assert
    // 等待用户消息显示
    await expect(page.locator('[data-testid="user-message"]').last())
      .toContainText('Hello, what can you do?');
    
    // 等待助手响应 (最多 30 秒)
    await expect(page.locator('[data-testid="assistant-message"]').last())
      .toBeVisible({ timeout: 30000 });
  });
  
  test('用户可以查看工具调用详情', async ({ page }) => {
    // Arrange
    await page.goto('/chat');
    
    // Act - 发送需要工具调用的消息
    await page.fill('[data-testid="chat-input"]', 'Read the file /etc/hostname');
    await page.click('[data-testid="send-button"]');
    
    // Assert - 检查工具调用展示
    await expect(page.locator('[data-testid="tool-call"]'))
      .toBeVisible({ timeout: 30000 });
    
    await expect(page.locator('[data-testid="tool-call"]'))
      .toContainText('read_file');
  });
  
  test('消息历史在页面刷新后保留', async ({ page }) => {
    // Arrange
    await page.goto('/chat');
    await page.fill('[data-testid="chat-input"]', 'Remember this: test123');
    await page.click('[data-testid="send-button"]');
    
    // 等待响应
    await expect(page.locator('[data-testid="assistant-message"]').last())
      .toBeVisible({ timeout: 30000 });
    
    // Act - 刷新页面
    await page.reload();
    
    // Assert - 消息仍然存在
    await expect(page.locator('[data-testid="user-message"]'))
      .toContainText('Remember this: test123');
  });
});
```

---

## 七、Fixtures 与 Mock 策略

### 7.1 全局 Fixtures

```python
# tests/conftest.py

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.db.database import Base


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine():
    """测试数据库引擎"""
    engine = create_async_engine(
        settings.test_database_url,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """数据库会话 (每个测试独立事务)"""
    async_session = sessionmaker(
        db_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()  # 回滚，不影响其他测试


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM Gateway"""
    from unittest.mock import AsyncMock
    
    gateway = AsyncMock()
    gateway.chat.return_value = MockLLMResponse(content="Mock response")
    gateway.chat_stream.return_value = mock_stream_response()
    
    return gateway


async def mock_stream_response():
    """Mock 流式响应"""
    chunks = ["Hello", " ", "world", "!"]
    for chunk in chunks:
        yield MockStreamChunk(content=chunk)


@pytest.fixture
def mock_tool_executor():
    """Mock 工具执行器"""
    from unittest.mock import AsyncMock
    from backend.core.types import ToolResult
    
    executor = AsyncMock()
    executor.execute.return_value = ToolResult(
        tool_call_id="test-call",
        success=True,
        result="Mock tool result",
        duration_ms=100
    )
    
    return executor
```

### 7.2 测试数据工厂

```python
# tests/fixtures/factories.py

import factory
from factory.alchemy import SQLAlchemyModelFactory
from datetime import datetime

from backend.models.user import User
from backend.models.agent import Agent
from backend.models.session import Session
from backend.models.message import Message


class UserFactory(SQLAlchemyModelFactory):
    """用户数据工厂"""
    
    class Meta:
        model = User
        sqlalchemy_session = None  # 运行时注入
    
    id = factory.Faker('uuid4')
    email = factory.Faker('email')
    name = factory.Faker('name')
    password_hash = "hashed_password"
    created_at = factory.LazyFunction(datetime.utcnow)


class AgentFactory(SQLAlchemyModelFactory):
    """Agent 数据工厂"""
    
    class Meta:
        model = Agent
        sqlalchemy_session = None
    
    id = factory.Faker('uuid4')
    user_id = factory.LazyAttribute(lambda obj: UserFactory().id)
    name = factory.Faker('word')
    system_prompt = "You are a helpful assistant."
    model = "gpt-4"
    tools = []
    config = {"temperature": 0.7}


class SessionFactory(SQLAlchemyModelFactory):
    """会话数据工厂"""
    
    class Meta:
        model = Session
        sqlalchemy_session = None
    
    id = factory.Faker('uuid4')
    user_id = factory.LazyAttribute(lambda obj: UserFactory().id)
    agent_id = factory.LazyAttribute(lambda obj: AgentFactory().id)
    status = "active"


class MessageFactory(SQLAlchemyModelFactory):
    """消息数据工厂"""
    
    class Meta:
        model = Message
        sqlalchemy_session = None
    
    id = factory.Faker('uuid4')
    session_id = factory.LazyAttribute(lambda obj: SessionFactory().id)
    role = "user"
    content = factory.Faker('sentence')


# 便捷函数
async def create_test_user(db_session, **kwargs):
    """创建测试用户"""
    UserFactory._meta.sqlalchemy_session = db_session
    user = UserFactory(**kwargs)
    db_session.add(user)
    await db_session.flush()
    return user


async def create_test_agent(db_session, user_id, **kwargs):
    """创建测试 Agent"""
    AgentFactory._meta.sqlalchemy_session = db_session
    agent = AgentFactory(user_id=user_id, **kwargs)
    db_session.add(agent)
    await db_session.flush()
    return agent
```

### 7.3 LLM Mock 策略

```python
# tests/mocks/llm_mock.py

from typing import AsyncIterator
from dataclasses import dataclass
from unittest.mock import AsyncMock

from backend.core.types import ToolCall


@dataclass
class MockLLMChunk:
    """Mock LLM 流式块"""
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None


class LLMMockBuilder:
    """LLM Mock 构建器"""
    
    def __init__(self):
        self.responses = []
        self.stream_chunks = []
    
    def with_text_response(self, content: str) -> "LLMMockBuilder":
        """添加文本响应"""
        self.responses.append({"type": "text", "content": content})
        return self
    
    def with_tool_call(
        self, 
        name: str, 
        arguments: dict,
        call_id: str = "call_123"
    ) -> "LLMMockBuilder":
        """添加工具调用"""
        self.responses.append({
            "type": "tool_call",
            "tool_call": ToolCall(id=call_id, name=name, arguments=arguments)
        })
        return self
    
    def with_stream(self, chunks: list[str]) -> "LLMMockBuilder":
        """添加流式块"""
        self.stream_chunks = chunks
        return self
    
    def build(self) -> AsyncMock:
        """构建 Mock 对象"""
        mock = AsyncMock()
        
        # 普通响应
        if self.responses:
            mock.chat.return_value = self._build_response()
        
        # 流式响应
        if self.stream_chunks:
            mock.chat_stream.return_value = self._stream_generator()
        
        return mock
    
    def _build_response(self):
        """构建响应对象"""
        response = AsyncMock()
        
        if self.responses[0]["type"] == "text":
            response.content = self.responses[0]["content"]
            response.tool_calls = None
        else:
            response.content = ""
            response.tool_calls = [r["tool_call"] for r in self.responses if r["type"] == "tool_call"]
        
        return response
    
    async def _stream_generator(self) -> AsyncIterator[MockLLMChunk]:
        """流式生成器"""
        for chunk in self.stream_chunks:
            yield MockLLMChunk(content=chunk)
        yield MockLLMChunk(finish_reason="stop")


# 使用示例
def create_simple_response_mock(content: str) -> AsyncMock:
    """创建简单文本响应 Mock"""
    return (
        LLMMockBuilder()
        .with_text_response(content)
        .build()
    )


def create_tool_call_mock(tool_name: str, arguments: dict) -> AsyncMock:
    """创建工具调用 Mock"""
    return (
        LLMMockBuilder()
        .with_tool_call(tool_name, arguments)
        .build()
    )
```

---

## 八、CI/CD 测试集成

### 8.1 GitHub Actions 配置

```yaml
# .github/workflows/test.yml

name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  # ========================================
  # 后端测试
  # ========================================
  backend-test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt -r requirements-dev.txt
      
      - name: Run type checking
        run: |
          cd backend
          pyright
      
      - name: Run linting
        run: |
          cd backend
          ruff check .
      
      - name: Run unit tests
        run: |
          cd backend
          pytest tests/unit -v --cov=backend --cov-report=xml -m "not slow"
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0
      
      - name: Run integration tests
        run: |
          cd backend
          pytest tests/integration -v --cov=backend --cov-report=xml --cov-append
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: backend/coverage.xml
          flags: backend
  
  # ========================================
  # 前端测试
  # ========================================
  frontend-test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'pnpm'
          cache-dependency-path: frontend/pnpm-lock.yaml
      
      - name: Install pnpm
        run: npm install -g pnpm
      
      - name: Install dependencies
        run: |
          cd frontend
          pnpm install
      
      - name: Run type checking
        run: |
          cd frontend
          pnpm tsc --noEmit
      
      - name: Run linting
        run: |
          cd frontend
          pnpm lint
      
      - name: Run unit tests
        run: |
          cd frontend
          pnpm test:coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: frontend/coverage/lcov.info
          flags: frontend
  
  # ========================================
  # E2E 测试
  # ========================================
  e2e-test:
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-test]  # 依赖单元测试通过
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Compose
        run: |
          docker compose -f deploy/docker/docker-compose.test.yml up -d
      
      - name: Wait for services
        run: |
          sleep 30
          curl --retry 10 --retry-delay 5 http://localhost:8000/api/v1/health
      
      - name: Install Playwright
        run: |
          cd frontend
          pnpm install
          pnpm exec playwright install --with-deps
      
      - name: Run E2E tests
        run: |
          cd frontend
          pnpm test:e2e
      
      - name: Upload E2E report
        uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: frontend/playwright-report/
      
      - name: Cleanup
        run: |
          docker compose -f deploy/docker/docker-compose.test.yml down -v
```

### 8.2 测试报告与覆盖率

```yaml
# .github/workflows/test.yml (续)

  # ========================================
  # 覆盖率检查
  # ========================================
  coverage-check:
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-test]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Download backend coverage
        uses: actions/download-artifact@v4
        with:
          name: backend-coverage
          path: coverage/
      
      - name: Download frontend coverage
        uses: actions/download-artifact@v4
        with:
          name: frontend-coverage
          path: coverage/
      
      - name: Check coverage threshold
        run: |
          # 检查后端覆盖率 >= 80%
          python -c "
          import xml.etree.ElementTree as ET
          tree = ET.parse('coverage/backend-coverage.xml')
          rate = float(tree.getroot().get('line-rate', 0))
          print(f'Backend coverage: {rate * 100:.1f}%')
          assert rate >= 0.8, f'Backend coverage {rate*100:.1f}% < 80%'
          "
          
          # 前端覆盖率检查类似
```

---

## 九、特殊场景测试

### 9.1 异步代码测试

```python
# 异步测试最佳实践

import pytest
import asyncio
from unittest.mock import AsyncMock


class TestAsyncCode:
    """异步代码测试"""
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        """测试异步函数"""
        result = await some_async_function()
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_async_generator(self):
        """测试异步生成器"""
        results = []
        async for item in some_async_generator():
            results.append(item)
        
        assert len(results) == expected_count
    
    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """测试并发执行"""
        results = await asyncio.gather(
            task1(),
            task2(),
            task3()
        )
        
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """测试超时处理"""
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                slow_function(),
                timeout=1.0
            )
    
    @pytest.mark.asyncio
    async def test_with_mock_async(self):
        """使用 AsyncMock"""
        mock_service = AsyncMock()
        mock_service.fetch_data.return_value = {"key": "value"}
        
        result = await mock_service.fetch_data("test")
        
        assert result["key"] == "value"
        mock_service.fetch_data.assert_called_once_with("test")
```

### 9.2 SSE 流测试

```python
# tests/integration/api/test_sse_stream.py

import pytest
from httpx import AsyncClient
import json


class TestSSEStream:
    """SSE 流式响应测试"""
    
    @pytest.mark.asyncio
    async def test_chat_sse_stream(self, client: AsyncClient, auth_headers):
        """测试 Chat SSE 流"""
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={"session_id": "test", "message": "Hi"},
            headers=auth_headers
        ) as response:
            events = []
            
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:])
                    events.append(data)
            
            # 验证事件序列
            event_types = [e["type"] for e in events]
            
            assert "thinking" in event_types
            assert "text" in event_types or "tool_call" in event_types
            assert event_types[-1] == "done"
    
    @pytest.mark.asyncio
    async def test_stream_error_handling(self, client: AsyncClient, auth_headers):
        """测试流错误处理"""
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={"session_id": "test", "message": "trigger_error"},
            headers=auth_headers
        ) as response:
            events = []
            
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:])
                    events.append(data)
            
            # 应该有错误事件
            error_events = [e for e in events if e["type"] == "error"]
            assert len(error_events) >= 1
```

### 9.3 Docker 沙箱测试

```python
# tests/integration/services/test_sandbox_executor.py

import pytest
from backend.services.sandbox_executor import SandboxExecutor


@pytest.mark.integration
@pytest.mark.docker
class TestSandboxExecutor:
    """Docker 沙箱执行器测试"""
    
    @pytest.fixture
    def executor(self):
        """创建执行器"""
        return SandboxExecutor()
    
    @pytest.mark.asyncio
    async def test_execute_simple_code(self, executor):
        """测试执行简单代码"""
        code = 'print("Hello, World!")'
        
        result = await executor.execute(code)
        
        assert result.success
        assert "Hello, World!" in result.stdout
        assert result.exit_code == 0
    
    @pytest.mark.asyncio
    async def test_execute_with_imports(self, executor):
        """测试带导入的代码"""
        code = '''
import json
data = {"key": "value"}
print(json.dumps(data))
'''
        
        result = await executor.execute(code)
        
        assert result.success
        assert '"key": "value"' in result.stdout
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, executor):
        """测试超时处理"""
        code = '''
import time
time.sleep(100)
'''
        
        result = await executor.execute(code, timeout=2)
        
        assert not result.success
        assert "timeout" in result.error.lower() or result.exit_code != 0
    
    @pytest.mark.asyncio
    async def test_memory_limit(self, executor):
        """测试内存限制"""
        code = '''
# 尝试分配大量内存
data = [0] * (1024 * 1024 * 1024)  # 1GB
'''
        
        result = await executor.execute(code)
        
        assert not result.success
    
    @pytest.mark.asyncio
    async def test_network_isolation(self, executor):
        """测试网络隔离"""
        code = '''
import urllib.request
urllib.request.urlopen("http://example.com")
'''
        
        result = await executor.execute(code)
        
        # 应该失败，因为网络被禁用
        assert not result.success
    
    @pytest.mark.asyncio
    async def test_syntax_error_captured(self, executor):
        """测试语法错误捕获"""
        code = 'def foo('  # 不完整的语法
        
        result = await executor.execute(code)
        
        assert not result.success
        assert "SyntaxError" in result.stderr
```

---

## 十、测试最佳实践

### 10.1 测试命名规范

```python
# ✅ 好的命名

def test_create_user_with_valid_email_succeeds():
    """有效邮箱创建用户成功"""
    pass

def test_create_user_with_invalid_email_raises_validation_error():
    """无效邮箱创建用户抛出验证错误"""
    pass

def test_token_counter_returns_zero_for_empty_string():
    """空字符串 token 计数返回 0"""
    pass


# ❌ 不好的命名

def test_1():
    """没有描述性"""
    pass

def test_user():
    """太笼统"""
    pass

def test_function():
    """没有说明测试什么"""
    pass
```

### 10.2 测试组织 (AAA 模式)

```python
def test_context_manager_builds_correct_message_order():
    """测试上下文管理器构建正确的消息顺序"""
    
    # Arrange (准备)
    context_manager = ContextManager(config)
    session_id = "test-session"
    user_input = "Hello"
    system_prompt = "You are helpful."
    
    # Act (执行)
    result = await context_manager.build(
        session_id=session_id,
        user_input=user_input,
        system_prompt=system_prompt
    )
    
    # Assert (断言)
    assert result.messages[0]["role"] == "system"
    assert result.messages[-1]["role"] == "user"
    assert result.messages[-1]["content"] == user_input
```

### 10.3 测试隔离原则

```python
# ✅ 好的实践: 每个测试独立

class TestUserService:
    
    @pytest.fixture
    def service(self, db_session):
        """每个测试获得新的 service 实例"""
        return UserService(db_session)
    
    def test_create_user(self, service):
        """测试 1: 创建用户"""
        user = service.create(email="test1@example.com")
        assert user.id is not None
    
    def test_get_user(self, service):
        """测试 2: 获取用户 - 不依赖测试 1"""
        # 自己创建需要的数据
        user = service.create(email="test2@example.com")
        
        found = service.get(user.id)
        assert found.email == "test2@example.com"


# ❌ 不好的实践: 测试间有依赖

class TestUserServiceBad:
    created_user_id = None  # 共享状态！
    
    def test_create_user(self, service):
        user = service.create(email="test@example.com")
        self.created_user_id = user.id  # 污染共享状态
    
    def test_get_user(self, service):
        # 依赖 test_create_user 先运行
        found = service.get(self.created_user_id)  # 可能为 None！
```

### 10.4 覆盖率目标

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              覆盖率目标                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  模块                          目标覆盖率        说明                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  核心业务逻辑                   ≥ 90%            关键路径必须覆盖            │
│  (Context Manager, Memory)                                                  │
│                                                                             │
│  工具系统                       ≥ 85%            每个工具都要测试            │
│  (Tool Registry, Executor)                                                  │
│                                                                             │
│  API 层                         ≥ 80%            主要端点覆盖                │
│  (Routes, Handlers)                                                         │
│                                                                             │
│  数据访问层                     ≥ 80%            CRUD 操作覆盖               │
│  (Repositories)                                                             │
│                                                                             │
│  工具函数                       ≥ 90%            纯函数易于测试              │
│  (Utils)                                                                    │
│                                                                             │
│  前端组件                       ≥ 75%            关键组件覆盖                │
│  (React Components)                                                         │
│                                                                             │
│  总体目标                       ≥ 80%            CI 门禁                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 十一、评估体系 (Evaluation)

### 11.1 评估框架总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Agent 评估体系                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         评估维度                                     │   │
│  │  ───────────────────────────────────────────────────────────────── │   │
│  │                                                                      │   │
│  │   功能正确性        质量评估          性能评估         用户体验       │   │
│  │   ──────────       ────────         ────────        ────────        │   │
│  │   • 任务完成率     • 输出质量        • 响应延迟      • 满意度        │   │
│  │   • 准确性        • 代码质量        • 吞吐量        • NPS 评分      │   │
│  │   • 一致性        • 安全合规        • 资源使用      • 留存率        │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         评估方法                                     │   │
│  │  ───────────────────────────────────────────────────────────────── │   │
│  │                                                                      │   │
│  │   自动化评估              LLM-as-Judge            人工评估           │   │
│  │   ────────────           ─────────────           ────────           │   │
│  │   • 基准测试集            • GPT-4 评分            • 专家评审         │   │
│  │   • 回归测试              • 多维度打分            • 用户反馈         │   │
│  │   • 指标计算              • 对比评估              • A/B 测试         │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 功能评估 (Functional Evaluation)

#### 11.2.1 任务完成率评估

```python
# evaluation/task_completion.py

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    SUCCESS = "success"           # 完全成功
    PARTIAL = "partial"           # 部分成功
    FAILED = "failed"             # 失败
    TIMEOUT = "timeout"           # 超时
    ERROR = "error"               # 错误


@dataclass
class TaskEvalResult:
    """任务评估结果"""
    task_id: str
    status: TaskStatus
    score: float                  # 0.0 - 1.0
    expected_output: str
    actual_output: str
    steps_taken: int
    time_taken_ms: int
    tokens_used: int
    errors: list[str]
    metadata: dict


class TaskEvaluator:
    """任务完成率评估器"""
    
    def __init__(self, test_cases: list[dict]):
        self.test_cases = test_cases
        self.results: list[TaskEvalResult] = []
    
    async def run_evaluation(self, agent) -> EvaluationReport:
        """运行评估"""
        for case in self.test_cases:
            result = await self._evaluate_single(agent, case)
            self.results.append(result)
        
        return self._generate_report()
    
    async def _evaluate_single(self, agent, case: dict) -> TaskEvalResult:
        """评估单个测试用例"""
        task_id = case["id"]
        input_prompt = case["input"]
        expected = case["expected_output"]
        criteria = case.get("criteria", {})
        
        start_time = time.time()
        
        try:
            # 执行 Agent
            response = await agent.run(input_prompt)
            
            # 评估输出
            score = await self._score_output(
                expected=expected,
                actual=response.content,
                criteria=criteria
            )
            
            status = self._determine_status(score, response)
            
            return TaskEvalResult(
                task_id=task_id,
                status=status,
                score=score,
                expected_output=expected,
                actual_output=response.content,
                steps_taken=response.iterations,
                time_taken_ms=int((time.time() - start_time) * 1000),
                tokens_used=response.total_tokens,
                errors=[],
                metadata={"criteria": criteria}
            )
            
        except Exception as e:
            return TaskEvalResult(
                task_id=task_id,
                status=TaskStatus.ERROR,
                score=0.0,
                expected_output=expected,
                actual_output="",
                steps_taken=0,
                time_taken_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                errors=[str(e)],
                metadata={}
            )
    
    def _generate_report(self) -> EvaluationReport:
        """生成评估报告"""
        total = len(self.results)
        success = sum(1 for r in self.results if r.status == TaskStatus.SUCCESS)
        partial = sum(1 for r in self.results if r.status == TaskStatus.PARTIAL)
        failed = sum(1 for r in self.results if r.status == TaskStatus.FAILED)
        
        return EvaluationReport(
            total_tasks=total,
            success_count=success,
            partial_count=partial,
            failed_count=failed,
            success_rate=success / total if total > 0 else 0,
            average_score=sum(r.score for r in self.results) / total if total > 0 else 0,
            average_time_ms=sum(r.time_taken_ms for r in self.results) / total if total > 0 else 0,
            average_tokens=sum(r.tokens_used for r in self.results) / total if total > 0 else 0,
            results=self.results
        )
```

#### 11.2.2 基准测试集

```yaml
# evaluation/benchmarks/agent_tasks.yaml

# 基准测试集配置
benchmark:
  name: "AI Agent Core Tasks"
  version: "1.0"
  categories:
    - name: "simple_qa"
      weight: 0.2
    - name: "tool_usage"
      weight: 0.3
    - name: "multi_step"
      weight: 0.3
    - name: "code_generation"
      weight: 0.2

test_cases:
  # =====================================
  # 简单问答
  # =====================================
  - id: "qa_001"
    category: "simple_qa"
    input: "What is 2 + 2?"
    expected_output: "4"
    criteria:
      exact_match: true
    
  - id: "qa_002"
    category: "simple_qa"
    input: "Summarize the benefits of TDD in one sentence."
    expected_output: null  # 使用 LLM-as-Judge
    criteria:
      contains_keywords: ["test", "quality", "design"]
      max_length: 100

  # =====================================
  # 工具使用
  # =====================================
  - id: "tool_001"
    category: "tool_usage"
    input: "Read the file /tmp/test.txt and tell me its contents."
    setup:
      - action: "create_file"
        path: "/tmp/test.txt"
        content: "Hello, World!"
    expected_output: "Hello, World!"
    criteria:
      must_use_tools: ["read_file"]
      
  - id: "tool_002"
    category: "tool_usage"
    input: "Search the web for the current weather in Beijing."
    expected_output: null
    criteria:
      must_use_tools: ["web_search"]
      response_contains: ["Beijing", "weather"]

  # =====================================
  # 多步骤任务
  # =====================================
  - id: "multi_001"
    category: "multi_step"
    input: |
      1. Read the file /tmp/data.json
      2. Extract the 'name' field
      3. Write it to /tmp/output.txt
    setup:
      - action: "create_file"
        path: "/tmp/data.json"
        content: '{"name": "Alice", "age": 30}'
    expected_output: null
    criteria:
      must_use_tools: ["read_file", "write_file"]
      verify_file:
        path: "/tmp/output.txt"
        contains: "Alice"

  # =====================================
  # 代码生成
  # =====================================
  - id: "code_001"
    category: "code_generation"
    input: "Write a Python function that calculates factorial."
    expected_output: null
    criteria:
      code_quality:
        syntax_valid: true
        has_docstring: true
        passes_tests:
          - input: [5]
            expected: 120
          - input: [0]
            expected: 1
```

### 11.3 LLM-as-Judge 评估

```python
# evaluation/llm_judge.py

from typing import Optional
from pydantic import BaseModel


class JudgeScore(BaseModel):
    """评分结果"""
    overall_score: float          # 0-10
    relevance: float              # 相关性
    accuracy: float               # 准确性
    completeness: float           # 完整性
    clarity: float                # 清晰度
    reasoning: str                # 评分理由


class LLMJudge:
    """LLM-as-Judge 评估器"""
    
    JUDGE_PROMPT = """You are an expert evaluator for AI assistant responses.

## Task
Evaluate the following response based on the given criteria.

## Input
**User Query:** {query}

**Expected Output (if any):** {expected}

**Actual Response:** {response}

## Evaluation Criteria
1. **Relevance (0-10):** Does the response address the user's query?
2. **Accuracy (0-10):** Is the information correct and factual?
3. **Completeness (0-10):** Does it fully answer the question?
4. **Clarity (0-10):** Is the response clear and well-structured?

## Output Format
Return a JSON object:
```json
{{
  "overall_score": 8.5,
  "relevance": 9,
  "accuracy": 8,
  "completeness": 8,
  "clarity": 9,
  "reasoning": "The response correctly addresses..."
}}
```

Evaluate now:"""

    def __init__(self, llm_gateway, judge_model: str = "gpt-4"):
        self.llm = agent_llm_facade
        self.judge_model = judge_model
    
    async def evaluate(
        self,
        query: str,
        response: str,
        expected: Optional[str] = None,
        criteria: Optional[dict] = None
    ) -> JudgeScore:
        """使用 LLM 评估响应质量"""
        
        prompt = self.JUDGE_PROMPT.format(
            query=query,
            expected=expected or "Not specified",
            response=response
        )
        
        result = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.judge_model,
            response_format={"type": "json_object"}
        )
        
        return JudgeScore.model_validate_json(result.content)
    
    async def compare(
        self,
        query: str,
        response_a: str,
        response_b: str
    ) -> dict:
        """对比两个响应"""
        
        compare_prompt = """Compare these two responses to the same query.

Query: {query}

Response A:
{response_a}

Response B:
{response_b}

Which response is better? Return JSON:
{{
  "winner": "A" or "B" or "tie",
  "score_a": 0-10,
  "score_b": 0-10,
  "reasoning": "..."
}}"""
        
        result = await self.llm.chat(
            messages=[{"role": "user", "content": compare_prompt.format(
                query=query,
                response_a=response_a,
                response_b=response_b
            )}],
            model=self.judge_model,
            response_format={"type": "json_object"}
        )
        
        return json.loads(result.content)


class MultiDimensionJudge:
    """多维度评估器"""
    
    DIMENSIONS = {
        "helpfulness": "How helpful is the response in addressing the user's needs?",
        "harmlessness": "Is the response free from harmful or dangerous content?",
        "honesty": "Is the response honest and not misleading?",
        "factuality": "Are the facts in the response accurate?",
        "coherence": "Is the response logically coherent and well-structured?",
    }
    
    async def evaluate_all_dimensions(
        self,
        query: str,
        response: str
    ) -> dict[str, float]:
        """评估所有维度"""
        scores = {}
        
        for dim, description in self.DIMENSIONS.items():
            score = await self._evaluate_dimension(
                query=query,
                response=response,
                dimension=dim,
                description=description
            )
            scores[dim] = score
        
        scores["overall"] = sum(scores.values()) / len(scores)
        return scores
```

### 11.4 代码质量评估

```python
# evaluation/code_quality.py

from dataclasses import dataclass
from typing import Optional
import ast
import subprocess


@dataclass
class CodeQualityScore:
    """代码质量评分"""
    syntax_valid: bool
    type_check_passed: bool
    lint_score: float              # 0-10
    test_pass_rate: float          # 0-1
    cyclomatic_complexity: float
    maintainability_index: float
    security_issues: list[str]
    suggestions: list[str]


class CodeQualityEvaluator:
    """代码质量评估器"""
    
    def __init__(self):
        pass
    
    async def evaluate(self, code: str, language: str = "python") -> CodeQualityScore:
        """评估代码质量"""
        
        # 1. 语法检查
        syntax_valid = self._check_syntax(code, language)
        
        # 2. 类型检查 (Python)
        type_check_passed = await self._run_type_check(code) if language == "python" else True
        
        # 3. Lint 检查
        lint_issues = await self._run_linter(code, language)
        lint_score = max(0, 10 - len(lint_issues) * 0.5)
        
        # 4. 复杂度分析
        complexity = self._analyze_complexity(code, language)
        
        # 5. 安全检查
        security_issues = await self._security_scan(code, language)
        
        # 6. 生成建议
        suggestions = self._generate_suggestions(
            lint_issues, complexity, security_issues
        )
        
        return CodeQualityScore(
            syntax_valid=syntax_valid,
            type_check_passed=type_check_passed,
            lint_score=lint_score,
            test_pass_rate=0.0,  # 需要单独运行测试
            cyclomatic_complexity=complexity.get("cyclomatic", 0),
            maintainability_index=complexity.get("maintainability", 0),
            security_issues=security_issues,
            suggestions=suggestions
        )
    
    def _check_syntax(self, code: str, language: str) -> bool:
        """语法检查"""
        if language == "python":
            try:
                ast.parse(code)
                return True
            except SyntaxError:
                return False
        return True  # 其他语言暂不支持
    
    async def _run_type_check(self, code: str) -> bool:
        """运行类型检查"""
        # 使用 pyright 检查
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            result = subprocess.run(
                ['pyright', temp_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception:
            return True  # 检查失败时默认通过
        finally:
            os.unlink(temp_path)
    
    async def _run_linter(self, code: str, language: str) -> list[dict]:
        """运行 Linter"""
        if language == "python":
            # 使用 ruff
            import tempfile
            import json
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                result = subprocess.run(
                    ['ruff', 'check', '--output-format=json', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.stdout:
                    return json.loads(result.stdout)
                return []
            except Exception:
                return []
            finally:
                os.unlink(temp_path)
        
        return []
```

### 11.5 性能评估

```python
# evaluation/performance.py

from dataclasses import dataclass
from typing import List
import time
import asyncio
import statistics


@dataclass
class PerformanceMetrics:
    """性能指标"""
    # 延迟指标 (ms)
    latency_p50: float
    latency_p90: float
    latency_p99: float
    latency_avg: float
    latency_min: float
    latency_max: float
    
    # 吞吐量
    requests_per_second: float
    
    # Token 指标
    tokens_per_second: float
    avg_tokens_per_request: float
    
    # 资源使用
    avg_memory_mb: float
    peak_memory_mb: float
    avg_cpu_percent: float


class PerformanceEvaluator:
    """性能评估器"""
    
    def __init__(self, agent, num_requests: int = 100, concurrency: int = 10):
        self.agent = agent
        self.num_requests = num_requests
        self.concurrency = concurrency
        self.results: List[dict] = []
    
    async def run_benchmark(self, test_prompts: list[str]) -> PerformanceMetrics:
        """运行性能基准测试"""
        
        # 准备请求
        prompts = test_prompts * (self.num_requests // len(test_prompts) + 1)
        prompts = prompts[:self.num_requests]
        
        # 并发执行
        semaphore = asyncio.Semaphore(self.concurrency)
        
        async def bounded_request(prompt: str) -> dict:
            async with semaphore:
                return await self._single_request(prompt)
        
        start_time = time.time()
        
        tasks = [bounded_request(p) for p in prompts]
        self.results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        return self._calculate_metrics(total_time)
    
    async def _single_request(self, prompt: str) -> dict:
        """执行单个请求"""
        start = time.time()
        
        try:
            response = await self.agent.run(prompt)
            
            return {
                "success": True,
                "latency_ms": (time.time() - start) * 1000,
                "tokens": response.total_tokens,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": (time.time() - start) * 1000,
                "tokens": 0,
                "error": str(e)
            }
    
    def _calculate_metrics(self, total_time: float) -> PerformanceMetrics:
        """计算性能指标"""
        
        latencies = [r["latency_ms"] for r in self.results if r["success"]]
        tokens = [r["tokens"] for r in self.results if r["success"]]
        
        latencies.sort()
        
        def percentile(data: list, p: float) -> float:
            if not data:
                return 0
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f])
        
        return PerformanceMetrics(
            latency_p50=percentile(latencies, 50),
            latency_p90=percentile(latencies, 90),
            latency_p99=percentile(latencies, 99),
            latency_avg=statistics.mean(latencies) if latencies else 0,
            latency_min=min(latencies) if latencies else 0,
            latency_max=max(latencies) if latencies else 0,
            requests_per_second=len(self.results) / total_time,
            tokens_per_second=sum(tokens) / total_time,
            avg_tokens_per_request=statistics.mean(tokens) if tokens else 0,
            avg_memory_mb=0,  # 需要额外监控
            peak_memory_mb=0,
            avg_cpu_percent=0
        )


class LoadTestRunner:
    """负载测试运行器"""
    
    async def run_load_test(
        self,
        agent,
        prompts: list[str],
        duration_seconds: int = 60,
        target_rps: float = 10
    ) -> dict:
        """
        运行负载测试
        
        Args:
            agent: Agent 实例
            prompts: 测试提示词
            duration_seconds: 测试持续时间
            target_rps: 目标每秒请求数
        """
        results = []
        start_time = time.time()
        request_interval = 1.0 / target_rps
        
        while time.time() - start_time < duration_seconds:
            prompt = random.choice(prompts)
            
            # 异步发送请求
            task = asyncio.create_task(self._timed_request(agent, prompt))
            results.append(task)
            
            await asyncio.sleep(request_interval)
        
        # 等待所有请求完成
        completed = await asyncio.gather(*results, return_exceptions=True)
        
        return self._analyze_load_test(completed, duration_seconds, target_rps)
```

### 11.6 用户体验评估

```python
# evaluation/user_experience.py

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class SatisfactionLevel(Enum):
    """满意度级别"""
    VERY_DISSATISFIED = 1
    DISSATISFIED = 2
    NEUTRAL = 3
    SATISFIED = 4
    VERY_SATISFIED = 5


@dataclass
class UserFeedback:
    """用户反馈"""
    session_id: str
    user_id: str
    satisfaction: SatisfactionLevel
    task_completed: bool
    would_recommend: bool  # NPS
    feedback_text: Optional[str]
    response_time_acceptable: bool
    accuracy_rating: int  # 1-5
    timestamp: datetime


class UserExperienceTracker:
    """用户体验追踪器"""
    
    def __init__(self, db):
        self.db = db
    
    async def record_feedback(self, feedback: UserFeedback):
        """记录用户反馈"""
        await self.db.save_feedback(feedback)
    
    async def calculate_nps(self, time_range_days: int = 30) -> float:
        """
        计算 NPS (Net Promoter Score)
        
        NPS = % Promoters - % Detractors
        - Promoters: would_recommend = True, satisfaction >= 4
        - Detractors: would_recommend = False, satisfaction <= 2
        """
        feedbacks = await self.db.get_feedbacks(days=time_range_days)
        
        if not feedbacks:
            return 0
        
        promoters = sum(1 for f in feedbacks 
                       if f.would_recommend and f.satisfaction.value >= 4)
        detractors = sum(1 for f in feedbacks 
                        if not f.would_recommend and f.satisfaction.value <= 2)
        
        total = len(feedbacks)
        nps = ((promoters - detractors) / total) * 100
        
        return round(nps, 1)
    
    async def get_satisfaction_distribution(self, time_range_days: int = 30) -> dict:
        """获取满意度分布"""
        feedbacks = await self.db.get_feedbacks(days=time_range_days)
        
        distribution = {level.name: 0 for level in SatisfactionLevel}
        
        for f in feedbacks:
            distribution[f.satisfaction.name] += 1
        
        return distribution
    
    async def generate_ux_report(self, time_range_days: int = 30) -> dict:
        """生成用户体验报告"""
        feedbacks = await self.db.get_feedbacks(days=time_range_days)
        
        return {
            "period_days": time_range_days,
            "total_feedbacks": len(feedbacks),
            "nps": await self.calculate_nps(time_range_days),
            "satisfaction_distribution": await self.get_satisfaction_distribution(time_range_days),
            "task_completion_rate": sum(1 for f in feedbacks if f.task_completed) / len(feedbacks) if feedbacks else 0,
            "avg_satisfaction": sum(f.satisfaction.value for f in feedbacks) / len(feedbacks) if feedbacks else 0,
            "avg_accuracy_rating": sum(f.accuracy_rating for f in feedbacks) / len(feedbacks) if feedbacks else 0,
            "response_time_acceptable_rate": sum(1 for f in feedbacks if f.response_time_acceptable) / len(feedbacks) if feedbacks else 0,
        }
```

### 11.7 评估流水线

```yaml
# evaluation/pipeline.yaml

# 评估流水线配置
evaluation_pipeline:
  name: "AI Agent Full Evaluation"
  schedule: "weekly"  # daily, weekly, on_release
  
  stages:
    # 阶段 1: 功能评估
    - name: "functional"
      evaluators:
        - type: "task_completion"
          config:
            benchmark: "agent_tasks.yaml"
            timeout_per_task: 60
        - type: "tool_usage"
          config:
            verify_correct_tool: true
            verify_parameters: true
      thresholds:
        success_rate: 0.9
        avg_score: 8.0
    
    # 阶段 2: 质量评估
    - name: "quality"
      evaluators:
        - type: "llm_judge"
          config:
            judge_model: "gpt-4"
            dimensions: ["relevance", "accuracy", "helpfulness"]
        - type: "code_quality"
          config:
            check_types: true
            check_lint: true
            check_security: true
      thresholds:
        avg_judge_score: 7.5
        code_quality_score: 8.0
    
    # 阶段 3: 性能评估
    - name: "performance"
      evaluators:
        - type: "latency"
          config:
            num_requests: 100
            concurrency: 10
        - type: "throughput"
          config:
            duration_seconds: 60
            target_rps: 20
      thresholds:
        p90_latency_ms: 3000
        min_rps: 15
    
    # 阶段 4: 回归检测
    - name: "regression"
      evaluators:
        - type: "comparison"
          config:
            baseline_version: "latest_release"
            compare_metrics: ["success_rate", "avg_score", "p90_latency"]
      thresholds:
        max_regression_percent: 5

  # 通知配置
  notifications:
    on_failure:
      - type: "slack"
        channel: "#ai-agent-alerts"
      - type: "email"
        recipients: ["team@example.com"]
    on_success:
      - type: "slack"
        channel: "#ai-agent-reports"

  # 报告配置
  reports:
    - format: "html"
      destination: "s3://reports/evaluation/"
    - format: "json"
      destination: "metrics_db"
```

### 11.8 评估指标仪表盘

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          评估指标仪表盘                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  关键指标 (KPIs)                                    更新: 2026-01-12 │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │                                                                      │   │
│  │   任务成功率          LLM 质量评分         P90 延迟          NPS     │   │
│  │   ┌──────────┐       ┌──────────┐       ┌──────────┐    ┌────────┐ │   │
│  │   │  92.5%   │       │   8.3    │       │  2.1s    │    │  +45   │ │   │
│  │   │   ↑2.1%  │       │   ↑0.2   │       │   ↓0.3s  │    │  ↑5    │ │   │
│  │   └──────────┘       └──────────┘       └──────────┘    └────────┘ │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  趋势图表                                                            │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │                                                                      │   │
│  │  任务成功率 (过去 30 天)                                             │   │
│  │  100%│                                      ╭───╮                   │   │
│  │   90%│    ╭────╮      ╭─────╮    ╭────╮   │   ╰─                   │   │
│  │   80%│───╯    ╰──────╯     ╰────╯    ╰───╯                         │   │
│  │   70%│                                                              │   │
│  │      └────────────────────────────────────────────────              │   │
│  │        W1      W2       W3       W4      W5     Now                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  分类评估结果                                                        │   │
│  │  ────────────────────────────────────────────────────────────────── │   │
│  │                                                                      │   │
│  │   类别              成功率    平均分    平均延迟    测试数           │   │
│  │   ─────────────────────────────────────────────────────────         │   │
│  │   简单问答          98.5%     9.2       0.8s       200              │   │
│  │   工具使用          91.2%     8.1       2.5s       150              │   │
│  │   多步骤任务        87.3%     7.8       4.2s       100              │   │
│  │   代码生成          89.6%     8.0       3.1s       120              │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.9 持续评估策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          持续评估策略                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  评估时机                执行内容                     目的                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  每次 PR                 • 核心功能基准测试           快速反馈              │
│                         • 关键路径回归测试                                  │
│                         • 代码质量检查                                      │
│                                                                             │
│  每日 (Nightly)         • 完整基准测试集             全面覆盖              │
│                         • 性能基准测试                                      │
│                         • LLM-as-Judge 抽样                                 │
│                                                                             │
│  每周                   • 全量 LLM 评估               深度分析              │
│                         • 用户反馈汇总                                      │
│                         • 对比历史版本                                      │
│                                                                             │
│  发布前                 • 完整评估流水线             质量门禁              │
│                         • 负载测试                                          │
│                         • 安全审计                                          │
│                         • 人工抽检                                          │
│                                                                             │
│  发布后                 • 线上指标监控               持续监控              │
│                         • 用户反馈收集                                      │
│                         • 异常检测告警                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 十二、总结

### 12.1 TDD 价值

| 价值 | 描述 |
|------|------|
| **设计驱动** | 先写测试迫使思考 API 设计 |
| **即时反馈** | 每次修改都有测试验证 |
| **文档作用** | 测试即文档，描述预期行为 |
| **重构信心** | 有测试保障，放心重构 |
| **减少 Bug** | 早期发现问题，降低修复成本 |

### 12.2 测试策略总结

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Agent 测试策略总结                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 纯业务逻辑 → 严格 TDD + 单元测试                                        │
│  2. 外部依赖 → Mock + 集成测试                                              │
│  3. LLM 交互 → Mock API + 少量真实测试                                      │
│  4. UI 组件 → 组件测试 + 快照测试                                           │
│  5. 关键流程 → E2E 测试                                                     │
│                                                                             │
│  覆盖率目标: 80%                                                            │
│  CI 门禁: 单元测试 + 类型检查 + Lint                                        │
│  定期运行: 集成测试 + E2E 测试                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 评估策略总结

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Agent 评估策略总结                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  评估维度:                                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  1. 功能评估 → 基准测试集 + 任务完成率                                      │
│  2. 质量评估 → LLM-as-Judge + 代码质量检查                                  │
│  3. 性能评估 → 延迟/吞吐量/资源使用                                         │
│  4. 用户体验 → NPS + 满意度 + 反馈收集                                      │
│                                                                             │
│  评估时机:                                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • PR 合并前: 核心功能回归测试                                              │
│  • 每日构建: 完整基准测试                                                   │
│  • 每周: 全量 LLM 评估 + 用户反馈分析                                       │
│  • 发布前: 完整评估流水线 + 人工审核                                        │
│                                                                             │
│  关键指标:                                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • 任务成功率 ≥ 90%                                                         │
│  • LLM 质量评分 ≥ 8.0                                                       │
│  • P90 延迟 ≤ 3s                                                            │
│  • NPS ≥ 40                                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

<div align="center">

**测试保障质量，评估驱动改进**

*文档版本: v1.1 | 最后更新: 2026-01-12*

</div>
