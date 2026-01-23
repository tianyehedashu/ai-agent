---
name: code-rule-check
model: fast
description: 对修改的代码进行全面检查，确保符合项目规范和质量标准。
---

# 代码规则检查清单

对修改的代码进行全面检查，确保符合项目规范和质量标准。

## 1. 架构符合性检查 (DDD 4层架构)

### 1.1 分层架构规范
- [ ] **表示层** (`domains/*/presentation/`): HTTP 路由、请求/响应 Schema，不包含业务逻辑
- [ ] **应用层** (`domains/*/application/`): UseCase 业务编排，事务协调
- [ ] **领域层** (`domains/*/domain/`): 实体、值对象、领域服务、仓储接口
- [ ] **基础设施层** (`domains/*/infrastructure/`): 仓储实现、ORM 模型、外部系统适配
- [ ] **共享层** (`shared/`): 跨领域共享的内核概念、基础设施、表示层组件

### 1.2 依赖方向检查
- [ ] 依赖方向正确：Presentation → Application → Domain ← Infrastructure
- [ ] 无循环依赖：使用 `TYPE_CHECKING` 处理类型引用
- [ ] 领域层不依赖基础设施层具体实现（依赖倒置）
- [ ] 表示层不直接访问基础设施层

### 1.3 模块职责检查
- [ ] 启动/配置代码放在 `bootstrap/`（FastAPI 入口、配置加载）
- [ ] Agent 引擎代码放在 `domains/runtime/infrastructure/engine/`
- [ ] 推理策略代码放在 `domains/runtime/infrastructure/reasoning/`
- [ ] 工具相关代码放在 `domains/runtime/infrastructure/tools/`
- [ ] 记忆相关代码放在 `domains/runtime/infrastructure/memory/`
- [ ] 沙箱执行器放在 `domains/runtime/infrastructure/sandbox/`
- [ ] 认证相关代码放在 `domains/identity/` 或 `shared/infrastructure/auth/`
- [ ] ORM 模型放在 `domains/*/infrastructure/models/`
- [ ] Pydantic Schema 放在 `domains/*/presentation/schemas.py` 或 `shared/presentation/`
- [ ] 共享依赖注入放在 `shared/presentation/deps.py`
- [ ] LLM 网关放在 `shared/infrastructure/llm/`
- [ ] 数据库连接放在 `shared/infrastructure/db/`
- [ ] TOML 配置文件放在 `config/`

## 2. 目录规范检查

### 2.1 文件命名规范
- [ ] 模块文件：`snake_case.py` (如 `user_use_case.py`)
- [ ] 路由文件：`*_router.py` (如 `session_router.py`)
- [ ] 测试文件：`test_<module>.py`，放在 `tests/` 对应目录

### 2.2 目录结构规范
```
backend/
├── api/v1/                 # API 路由汇总（表现层入口）
│   └── router.py           # 极简，仅导入各领域路由
├── bootstrap/              # 启动层：FastAPI 入口、配置
│   ├── main.py             # FastAPI 应用入口
│   ├── config.py           # 应用配置
│   └── config_loader.py    # TOML 配置加载器
├── domains/                # 业务领域 (DDD)
│   ├── agent_catalog/      # Agent 目录管理
│   ├── evaluation/         # 评估领域
│   ├── identity/           # 身份认证
│   ├── runtime/            # Agent 运行时（核心）
│   │   ├── application/    # UseCase
│   │   ├── domain/         # 实体/领域服务
│   │   ├── infrastructure/ # 基础设施
│   │   │   ├── engine/     # LangGraph Agent 引擎
│   │   │   ├── memory/     # 记忆系统
│   │   │   ├── reasoning/  # 推理策略 (ReAct/CoT/ToT)
│   │   │   ├── sandbox/    # 沙箱执行器
│   │   │   └── tools/      # 工具系统
│   │   └── presentation/   # 路由 + Schema
│   └── studio/             # 工作室领域
├── shared/                 # 共享层
│   ├── kernel/             # 内核类型 (Principal 等)
│   ├── infrastructure/     # 共享基础设施
│   │   ├── auth/           # 认证工具 (JWT/密码/RBAC)
│   │   ├── config/         # 配置服务
│   │   ├── db/             # 数据库连接
│   │   ├── llm/            # LLM 网关
│   │   ├── middleware/     # 中间件
│   │   ├── observability/  # 可观测性
│   │   └── orm/            # ORM 基类
│   ├── presentation/       # 共享表示层（deps, errors, schemas）
│   ├── types.py            # 核心类型定义
│   └── interfaces.py       # 接口定义
├── utils/                  # 工具函数
├── evaluation/             # 评估框架
├── config/                 # TOML 配置文件
└── tests/                  # 测试目录
```

**目录说明**：
- `api/v1/` - 表现层入口，路由聚合，导入 `shared.presentation` 的依赖
- `bootstrap/` - 启动层，负责初始化 FastAPI 应用、配置和生命周期管理
- `shared/presentation/` - 共享的表示层组件：依赖注入、错误常量、Schema

### 2.3 导入规范
- [ ] 导入顺序：标准库 → 第三方库 → 本地模块
- [ ] 使用绝对导入：`from domains.identity.application import UserUseCase`
- [ ] 避免 `from X import *`
- [ ] 类型检查时使用 `TYPE_CHECKING` 避免循环依赖
- [ ] 从领域层导入 Schema：`from domains.identity.presentation.schemas import UserCreate`
- [ ] 从共享层导入依赖注入：`from shared.presentation.deps import get_current_principal`
- [ ] 从共享层导入类型：`from shared.types import Result, AgentConfig, EventType`

## 3. 软件工程最佳实践

### 3.1 类型安全
- [ ] 所有函数参数和返回值有完整类型注解
- [ ] 类属性有类型注解（使用 `Mapped[T]` 用于 SQLAlchemy）
- [ ] 通过 `pyright --strict` 类型检查
- [ ] 优先使用 `shared/types.py` 中定义的类型：
  - `Result[T]` - 结果类型
  - `AgentConfig`, `AgentState` - Agent 配置/状态
  - `EventType`, `AgentEvent` - 事件系统
  - `ToolProtocol`, `ToolCall`, `ToolResult` - 工具协议
  - `CheckpointerProtocol`, `Checkpoint` - 检查点协议
- [ ] 使用 `shared/kernel/types.py` 中的内核类型 (`Principal`)

### 3.2 代码风格
- [ ] 符合 Ruff 配置（已在 `pyproject.toml`）
- [ ] 行长度不超过 100 字符
- [ ] 使用 `pathlib.Path` 而非 `os.path`
- [ ] 使用 f-string 而非 `.format()` 或 `%` 格式化

### 3.3 错误处理
- [ ] 使用 `Result[T]` 类型处理可能失败的操作
- [ ] 自定义异常继承自 `AIAgentError`（在 `exceptions.py`）
- [ ] 常用异常类型：
  - `ValidationError` - 验证失败
  - `NotFoundError` - 资源不存在
  - `PermissionDeniedError` - 权限不足
  - `AuthenticationError` / `TokenError` - 认证问题
  - `ToolExecutionError` - 工具执行失败
  - `ExternalServiceError` - 外部服务错误
- [ ] API 层将业务异常转换为 HTTP 异常
- [ ] 异步操作有适当的异常处理

### 3.4 异步编程
- [ ] 数据库操作使用 `AsyncSession`
- [ ] I/O 操作使用 `async/await`
- [ ] 并发操作使用 `asyncio.gather()` 或 `asyncio.Semaphore`
- [ ] 流式响应使用 `AsyncGenerator`

### 3.5 文档与注释
- [ ] 模块有文档字符串说明用途
- [ ] 公共函数/方法有 Google 风格文档字符串
- [ ] 复杂逻辑有行内注释（解释"为什么"而非"是什么"）
- [ ] 类型注解足够清晰，减少注释需求

## 4. 设计合理性检查

### 4.1 避免过度设计
- [ ] 不引入不必要的抽象层
- [ ] 不创建"未来可能用到"的接口
- [ ] 不添加未使用的配置项
- [ ] 不实现超出当前需求的复杂模式

### 4.2 单一职责原则
- [ ] 每个函数只做一件事
- [ ] 每个类有明确的单一职责
- [ ] 模块职责边界清晰

### 4.3 开闭原则
- [ ] 对扩展开放：使用 Protocol 定义接口
- [ ] 对修改封闭：核心逻辑稳定，通过配置扩展

## 5. 代码复用检查

### 5.1 避免重复造轮子
- [ ] 优先使用 `shared/types.py` 中的类型定义
- [ ] 复用 `domains/*/application/` 中的 UseCase
- [ ] 使用 `domains/runtime/infrastructure/tools/` 中的工具而非重新实现
- [ ] 复用 `utils/` 中的工具函数：
  - `utils/serialization.py` - 序列化工具
  - `utils/tokens.py` - Token 计算
  - `utils/cache.py` - 缓存工具
  - `utils/crypto.py` - 加密工具

### 5.2 抽象复用
- [ ] 相似逻辑提取为公共函数/类
- [ ] 使用基类/Protocol 定义通用接口
- [ ] 配置化而非硬编码
- [ ] ORM 模型继承自 `shared.infrastructure.orm.base.BaseModel`
- [ ] 使用 `shared/infrastructure/llm/gateway.py` 调用 LLM

### 5.3 依赖检查
- [ ] 检查是否有现成的第三方库可用
- [ ] 避免实现标准库已有的功能
- [ ] 优先使用项目已集成的库

## 6. 质量检查工具验证

### 6.1 静态检查
- [ ] 通过 `ruff check` 代码检查

### 6.2 测试覆盖
- [ ] 新功能有对应的单元测试
- [ ] 关键路径有集成测试
- [ ] 测试命名清晰：`test_<scenario>_<expected_result>`

## 7. 性能与安全

### 7.1 性能考虑
- [ ] 数据库查询使用索引字段
- [ ] 避免 N+1 查询问题
- [ ] 批量操作使用批量 API
- [ ] 异步操作正确使用 `await`

### 7.2 安全考虑
- [ ] 用户输入有验证（使用 Pydantic Schema）
- [ ] 敏感操作有权限检查
- [ ] 无 SQL 注入风险（使用 ORM 查询）
- [ ] 无路径遍历风险（使用 `pathlib` 规范化路径）

---

**检查原则**: 优先复用、符合 DDD 架构、类型安全、避免过度设计
