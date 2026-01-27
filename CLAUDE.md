# AI Agent 项目规范

## 架构概览

```
backend/
├── domains/                 # 业务域
│   ├── identity/            # 身份认证域
│   │   ├── domain/types.py  # Principal, ANONYMOUS_*
│   │   └── presentation/    # 认证依赖、中间件
│   ├── agent/               # Agent 域（核心业务域）
│   │   ├── domain/
│   │   │   ├── types.py     # Message, AgentEvent, ToolCall
│   │   │   └── entities/    # AgentEntity, SessionDomainService
│   │   ├── application/     # AgentUseCase, ChatUseCase, SessionUseCase
│   │   └── infrastructure/
│   │       ├── llm/         # LLM 网关
│   │       ├── memory/      # 记忆系统
│   │       ├── tools/       # 工具系统
│   │       └── reasoning/   # 推理策略
│   ├── studio/              # 工作室域（工作流）
│   └── evaluation/          # 评估域
├── libs/                    # 纯技术基础设施（非业务）
│   ├── types/               # 通用工具类型 (Result[T])
│   ├── config/              # 配置管理
│   ├── db/                  # 数据库组件
│   └── api/                 # 服务工厂、错误常量
└── bootstrap/               # 应用启动
```

## 类型安全

| 语言 | 复用 | 禁止 |
|------|------|------|
| Python | `domains.*.domain.types`, `libs.*` | `Any`, `dict` 无类型, `# type: ignore` |
| TypeScript | `@/types`, `@/stores` | `any`, `as any`, `@ts-ignore`, 直接操作 `localStorage` |

## 导入规范

```python
# 身份类型
from domains.identity.domain.types import Principal, ANONYMOUS_ID_PREFIX

# 认证依赖（从 identity 域）
from domains.identity.presentation.deps import AuthUser, RequiredAuthUser, check_session_ownership
from domains.identity.presentation.schemas import CurrentUser

# Agent 域类型
from domains.agent.domain.types import Message, AgentEvent, EventType, ToolCall

# Agent 域组件
from domains.agent.infrastructure.llm import LLMGateway
from domains.agent.infrastructure.tools import ConfiguredToolRegistry
from domains.agent.application import ChatUseCase, SessionUseCase

# 纯技术基础设施
from libs.config import ExecutionConfig
from libs.api.deps import get_db, get_session_service  # 服务工厂
from libs.types import Result
```

## 原则

- **DRY** - 复用现有类型和工具函数
- **分层** - Presentation / Application / Domain / Infrastructure
- **业务/技术分离** - 业务类型在 `domains/`，纯技术基础设施在 `libs/`

## 详细规范

[backend/docs/CODE_STANDARDS.md](backend/docs/CODE_STANDARDS.md) | [frontend/docs/CODE_STANDARDS.md](frontend/docs/CODE_STANDARDS.md)
