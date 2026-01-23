# Core 目录架构说明

## 架构定位

当前项目采用**混合架构**，适合 AI Agent 系统的特点：

```
backend/
├── domains/    # 业务领域（DDD 四层）- 会话、用户、Agent 目录等
├── core/       # Agent 技术能力层 - 引擎、LLM、推理、沙箱等
├── shared/     # 共享类型和工具
└── db/         # 数据库连接
```

## 为什么这样设计是合理的

### 1. AI Agent 系统的特殊性

对于 AI Agent 系统，`core/` 中的内容是**核心能力**，不仅仅是基础设施：

| 模块 | 职责 | 为什么是核心 |
|------|------|-------------|
| `engine/` | Agent 执行引擎 | Agent 的大脑，决定如何运行 |
| `llm/` | LLM 网关 | Agent 的智能来源 |
| `reasoning/` | 推理模式 | Agent 的思考方式 |
| `memory/` | 记忆系统 | Agent 的知识存储 |
| `sandbox/` | 沙箱执行 | Agent 的行动能力 |
| `context/` | 上下文管理 | Agent 的感知能力 |

这与传统 CRUD 应用不同 —— 传统应用的"核心"是业务规则，而 AI Agent 的"核心"是智能能力。

### 2. 实用主义 > 教条主义

- ✅ 当前架构能工作，代码清晰
- ✅ 团队容易理解和维护
- ❌ 不需要为了符合教科书式 DDD 而过度设计

### 3. 各层职责

```
domains/*/presentation   → HTTP 路由、请求响应
domains/*/application    → 用例编排、调用 core 能力
domains/*/domain         → 业务实体、规则
domains/*/infrastructure → 数据持久化

core/                    → Agent 技术能力（被 application 调用）
shared/                  → 跨域共享的类型和工具
```

## 使用规范

### 正确的依赖方向

```python
# domains/runtime/application/chat_use_case.py

# ✅ 正确：application 层调用 core 能力
from core.engine.langgraph_agent import LangGraphAgentEngine
from core.llm.gateway import LLMGateway

# ✅ 正确：application 层调用 domain 层
from domains.runtime.domain.entities.session import Session
```

### 避免的做法

```python
# ❌ 错误：presentation 层直接调用 core
# 应该通过 application 层间接调用

# ❌ 错误：core 模块之间循环依赖
# 保持 core 内部模块相对独立
```

## 何时考虑重构

只有在以下情况才需要考虑架构调整：

1. **需要替换实现** - 如从 LangGraph 切换到其他框架，此时可以引入接口层
2. **需要多租户** - 不同租户使用不同的 LLM/沙箱配置
3. **性能瓶颈** - 需要对特定能力进行独立扩展

**当前阶段**：专注于功能实现，保持架构简单。
