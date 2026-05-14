---
name: code-rule-check
model: composer-2
description: 对修改的代码进行全面检查,确保符合项目规范和质量标准。
---

# 代码规则检查清单

对修改的代码进行全面检查,确保符合项目规范和质量标准。

## 1. 架构符合性检查 (DDD 4层架构)

### 1.1 分层架构规范
- [ ] **表示层** (`domains/*/presentation/`): HTTP 路由、请求/响应 Schema,不包含业务逻辑
- [ ] **应用层** (`domains/*/application/`): UseCase 业务编排,事务协调
- [ ] **领域层** (`domains/*/domain/`): 实体、值对象、领域服务、仓储接口
- [ ] **基础设施层** (`domains/*/infrastructure/`): 仓储实现、ORM 模型、外部系统适配
- [ ] **纯技术层** (`libs/`): 跨领域共享的技术基础设施(非业务)

### 1.2 依赖方向检查
- [ ] 依赖方向正确: Presentation → Application → Domain ← Infrastructure
- [ ] 无循环依赖: 使用 `TYPE_CHECKING` 处理类型引用
- [ ] 领域层不依赖基础设施层具体实现(依赖倒置)
- [ ] 表示层不直接访问基础设施层
- [ ] 业务类型在 `domains/`,纯技术基础设施在 `libs/`

### 1.3 模块职责检查
- [ ] 启动/配置代码放在 `bootstrap/`（FastAPI 入口、配置加载）
- [ ] Agent 引擎代码放在 `domains/agent/infrastructure/llm/`
- [ ] 推理策略代码放在 `domains/agent/infrastructure/reasoning/`
- [ ] 工具相关代码放在 `domains/agent/infrastructure/tools/`
- [ ] 记忆相关代码放在 `domains/agent/infrastructure/memory/`
- [ ] 认证相关代码放在 `domains/identity/domain/types.py` 和 `presentation/deps.py`
- [ ] 会话应用端口 `SessionApplicationPort` 在 `domains/session/application/ports.py`（**不在** `libs/`）
- [ ] Gateway 内部桥接端口 `GatewayProxyProtocol`、`GatewayCallContext` 等在 `domains/gateway/application/ports.py`；工厂 `get_gateway_proxy` 在 `gateway_proxy_factory.py`（**不在** `libs/gateway`，该路径已废弃）
- [ ] 团队/成员权威在 `domains/tenancy/`；Gateway 管理面经 `TeamService` / 仓储访问团队，不复制 tenancy 规则
- [ ] ORM 模型放在 `domains/*/infrastructure/models/`
- [ ] Pydantic Schema 放在 `domains/*/presentation/schemas.py` 或 `presentation/schemas/` 分包
- [ ] 数据库连接/会话工厂放在 `libs/db/`
- [ ] 通用类型定义放在 `libs/types/`
- [ ] 配置管理放在 `libs/config/`
- [ ] API 服务工厂/依赖注入放在 `libs/api/deps.py`
- [ ] 跨域 IAM 抽象（如 `MembershipPort`）在 `libs/iam/`，业务团队规则不在 `libs`

## 2. 目录规范检查

### 2.1 文件命名规范
- [ ] 模块文件: `snake_case.py` (如 `user_use_case.py`)
- [ ] 路由文件: `*_router.py` (如 `session_router.py`)
- [ ] 测试文件: `test_<module>.py`,放在 `tests/` 对应目录

### 2.2 目录结构规范

（细目以 `backend/docs/CODE_STANDARDS.md` 为准；下列为检查用缩略树。）

```
backend/
├── domains/                      # 业务限界上下文
│   ├── identity/                 # 身份、JWT、API Key
│   ├── session/                  # 会话；application/ports.py = SessionApplicationPort
│   ├── tenancy/                  # 团队与成员权威
│   ├── gateway/                  # AI Gateway；application/ports.py = GatewayProxyProtocol 等
│   │   └── application/
│   │       ├── ports.py
│   │       ├── gateway_proxy_factory.py
│   │       ├── internal_bridge.py
│   │       ├── management/       # 管理面 CQRS 读写
│   │       └── ...
│   ├── agent/                    # Agent 核心
│   │   ├── application/
│   │   ├── infrastructure/llm/   # 可依赖 domains.gateway.application.ports（不依赖 gateway 实现细节）
│   │   └── presentation/
│   └── evaluation/
├── libs/                         # 纯技术：db、config、api、exceptions、iam、middleware、observability、orm…
├── bootstrap/
└── tests/                        # unit / integration / e2e
```

**目录说明**：

- `domains/*/`：每域四层齐全时，保持 **presentation → application → domain ← infrastructure**。
- **`application/ports.py`**：跨域 **应用端口（Protocol）** 的默认落点之一（与 gateway 分散的 `ports.py` + 桥接辅助模块同属应用层约定）。
- `libs/`：无业务规则；**不**新增「某 BC 的业务协议包」到 `libs/`。
- `bootstrap/`：组装与进程生命周期。

### 2.3 导入规范

#### 2.3.1 导入顺序
- [ ] 导入顺序: 标准库 → 第三方库 → 本地模块

#### 2.3.2 业务类型导入
```python
# 身份类型 (从 identity 域)
from domains.identity.domain.types import Principal, ANONYMOUS_ID_PREFIX

# 认证依赖 (从 identity 域)
from domains.identity.presentation.deps import AuthUser, RequiredAuthUser, check_session_ownership
from domains.identity.presentation.schemas import CurrentUser

# Agent 域类型
from domains.agent.domain.types import Message, AgentEvent, EventType, ToolCall
```

#### 2.3.3 业务组件导入
```python
# Agent 域组件（Chat/Video 依赖 SessionApplicationPort，组合根注入 SessionUseCase）
from domains.agent.application import ChatUseCase
from domains.session.application import SessionUseCase
from domains.session.application.ports import SessionApplicationPort
from domains.agent.infrastructure.llm import LLMGateway
from domains.agent.infrastructure.tools import ConfiguredToolRegistry

# 内部 LLM 走 Gateway 桥接时（端口在 gateway 应用层）
from domains.gateway.application.ports import GatewayCallContext, GatewayProxyProtocol
from domains.gateway.application.gateway_proxy_factory import get_gateway_proxy
```

#### 2.3.4 技术基础设施导入
```python
# 配置管理
from libs.config import ExecutionConfig

# 服务工厂/依赖注入
from libs.api.deps import get_db, get_session_service

# 通用类型
from libs.types import Result
```

#### 2.3.5 导入规范
- [ ] 使用绝对导入: `from domains.identity.application import UserUseCase`
- [ ] 避免 `from X import *`
- [ ] 类型检查时使用 `TYPE_CHECKING` 避免循环依赖
- [ ] 业务类型从 `domains.*.domain.types` 导入
- [ ] 认证依赖从 `domains.identity.presentation.deps` 导入
- [ ] 技术类型从 `libs.*` 导入

## 3. 软件工程最佳实践

### 3.1 类型安全
- [ ] 所有函数参数和返回值有完整类型注解
- [ ] 类属性有类型注解(使用 `Mapped[T]` 用于 SQLAlchemy)
- [ ] 通过 `pyright --strict` 类型检查
- [ ] 禁止使用:
  - `Any`
  - `dict` 无类型注解
  - `# type: ignore` (除非绝对必要)
- [ ] 优先使用已定义的类型:
  - `domains.*.domain.types` 中的业务类型
  - `libs.types` 中的通用类型 (如 `Result[T]`)

### 3.2 代码风格
- [ ] 符合 Ruff 配置(已在 `pyproject.toml`)
- [ ] 行长度不超过 100 字符
- [ ] 使用 `pathlib.Path` 而非 `os.path`
- [ ] 使用 f-string 而非 `.format()` 或 `%` 格式化

### 3.3 错误处理
- [ ] 使用 `Result[T]` 类型处理可能失败的操作
- [ ] 自定义异常继承自 `AIAgentError`（定义在 `libs/exceptions`）
- [ ] 常用异常类型:
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
- [ ] 复杂逻辑有行内注释(解释"为什么"而非"是什么")
- [ ] 类型注解足够清晰,减少注释需求

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
- [ ] 对扩展开放: 使用 Protocol 定义接口
- [ ] 对修改封闭: 核心逻辑稳定,通过配置扩展

### 4.4 业务/技术分离
- [ ] 业务逻辑放在 `domains/`
- [ ] 纯技术工具放在 `libs/`
- [ ] `libs/` 中不包含业务概念；**跨域应用端口（Protocol + 业务相关 DTO）** 放在 **`domains/<provider>/application/`**，不放入 `libs/` 以免与「纯技术」混淆
- [ ] `domains/` 中避免复制 `libs` 已有能力（DB 会话、通用 Result 等应复用 `libs`）

## 5. 代码复用检查

### 5.1 避免重复造轮子
- [ ] 优先使用 `domains.*.domain.types` 中的业务类型
- [ ] 复用 `domains/*/application/` 中的 UseCase
- [ ] 使用 `domains/agent/infrastructure/tools/` 中的工具而非重新实现
- [ ] 复用 `libs/` 中的技术组件:
  - `libs/types/` - 通用类型
  - `libs/config/` - 配置管理
  - `libs/db/` - 数据库组件
  - `libs/api/` - API 工具

### 5.2 抽象复用
- [ ] 相似逻辑提取为公共函数/类
- [ ] 使用基类/Protocol 定义通用接口
- [ ] 配置化而非硬编码
- [ ] ORM 模型继承自基类(如果存在)
- [ ] 使用统一的 LLM 网关

### 5.3 依赖检查
- [ ] 检查是否有现成的第三方库可用
- [ ] 避免实现标准库已有的功能
- [ ] 优先使用项目已集成的库

## 6. 质量检查工具验证

### 6.1 静态检查
- [ ] 通过 `ruff check` 代码检查
- [ ] 通过 `pyright` 类型检查
- [ ] 通过 `mypy` 类型检查(如果启用)

### 6.2 测试覆盖
- [ ] 新功能有对应的单元测试
- [ ] 关键路径有集成测试
- [ ] 测试命名清晰: `test_<scenario>_<expected_result>`

## 7. 性能与安全

### 7.1 性能考虑
- [ ] 数据库查询使用索引字段
- [ ] 避免 N+1 查询问题
- [ ] 批量操作使用批量 API
- [ ] 异步操作正确使用 `await`

### 7.2 安全考虑
- [ ] 用户输入有验证(使用 Pydantic Schema)
- [ ] 敏感操作有权限检查(使用 `check_session_ownership`)
- [ ] 无 SQL 注入风险(使用 ORM 查询)
- [ ] 无路径遍历风险(使用 `pathlib` 规范化路径)

## 8. 前端代码检查 (TypeScript)

### 8.1 类型安全
- [ ] 所有变量/函数/参数有类型注解
- [ ] 禁止使用 `any`, `as any`, `@ts-ignore`
- [ ] 优先使用 `@/types` 中的类型定义

### 8.2 导入规范
- [ ] 业务类型从对应的域导入
- [ ] 通用类型从 `@/types` 导入
- [ ] 使用相对路径 `@/` 导入项目模块

---

**检查原则**: 优先复用、符合 DDD 架构、类型安全、业务/技术分离、避免过度设计
