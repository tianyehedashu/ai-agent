# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

### 开发环境

```bash
# 启动基础服务 (PostgreSQL, Redis, Qdrant)
make docker-services

# 后端 (在 backend/ 目录下)
cd backend && make sync          # 安装/同步依赖 (uv)
cd backend && make dev           # 启动后端开发服务器 (uvicorn --reload)
cd backend && make db-upgrade    # 数据库迁移到最新版本

# 前端 (在 frontend/ 目录下)
cd frontend && npm install       # 安装依赖
cd frontend && npm run dev       # 启动前端开发服务器 (Vite)
```

### 测试

```bash
# 后端测试 (并发执行，通过 PYTEST_NUM_WORKERS 控制并发数)
cd backend && make test                      # 单元+集成测试 (不含 E2E)
cd backend && make test-e2e                  # E2E 测试
cd backend && PYTEST_NUM_WORKERS=4 make test # 指定并发数

# 前端测试
cd frontend && npm run test:run              # 运行 Vitest
cd frontend && npm run test:coverage         # 含覆盖率报告
```

### 代码质量

```bash
cd backend && make check    # lint (ruff) + typecheck (pyright --strict) + format check
cd frontend && npm run check # typecheck + lint + format check
cd frontend && npm run fix   # 自动修复 lint + format
```

### Docker 部署

```bash
make docker-up       # 开发环境全服务启动
make deploy          # 部署到远程 web01 (PowerShell 脚本)
make deploy-quick    # 快速部署 (仅同步代码+重启)
```

## 架构概览

### 后端分层 (DDD 四层)

```
backend/
├── bootstrap/          # FastAPI 入口、生命周期、路由注册、组合根
├── domains/            # 业务限界上下文 (每个子目录一个域)
│   ├── identity/       # 身份认证: Principal, JWT, API Key, User ORM
│   ├── session/        # 会话: Session CRUD, 标题生成, SessionApplicationPort
│   ├── tenancy/        # 团队/成员权威: Team, TeamMember, TeamService
│   ├── gateway/        # AI Gateway: /v1/* (OpenAI+Anthropic 兼容入口), 模型路由, 凭据, 预算, 日志
│   ├── agent/          # Agent 核心: ReAct 循环, 工具系统, 记忆, MCP, LLM 桥接
│   └── evaluation/     # 评估接口
├── libs/               # 纯技术基础设施 (无业务规则)
│   ├── types/          # Result[T] 等通用代数类型
│   ├── config/         # ExecutionConfig, 多来源配置加载
│   ├── db/             # AsyncSession 工厂, Redis, 向量库
│   ├── api/            # get_*_service 组合根, 分页, 错误常量
│   ├── exceptions/     # AIAgentError 异常层次
│   ├── iam/            # 跨域 IAM 抽象: TenantId, MembershipPort
│   ├── middleware/     # 日志, trace, 限流, 匿名 Cookie
│   └── orm/            # DeclarativeBase 等 ORM 基类
├── alembic/            # 数据库迁移
└── tests/              # 后端测试
```

每个业务域内遵循: `presentation/` → `application/` → `domain/` ← `infrastructure/`

### 前端结构

```
frontend/src/
├── api/           # HTTP 请求封装 (axios/fetch)
├── components/    # 通用组件 (ui/, layout/, shared/)
├── features/      # 按功能分包的业务组件 (gateway-credentials, gateway-models 等)
├── hooks/         # 自定义 Hooks
├── lib/           # 工具函数
├── pages/         # 页面组件
├── routes/        # 路由配置
├── stores/        # Zustand 全局状态
└── types/         # TypeScript 类型定义
```

路径别名: `@/*` → `src/`

### 关键设计决策

- **Agent LLM 桥接**: `domains/agent/infrastructure/llm/agent_llm_facade.py` 仅做领域消息与 Gateway 的桥接，provider 适配、凭据、Prompt Cache 等全部在 `domains/gateway/` 处理
- **Gateway 管理面 CQRS**: `application/management/` 下分包读写服务 (`GatewayManagementReadService` / `GatewayManagementWriteService`)，鉴权统一走 `GatewayAccessUseCase`
- **内部调用**: Agent 调用 LLM 不直连外部 API，而是通过 `GatewayBridge` (LiteLLM + 系统 vkey) 走内部 Gateway
- **团队解析**: 团队权威在 `domains/tenancy/`，Gateway 管理 API 通过 `TeamService` 访问
- **分页规范**: 见 `docs/PAGINATION.md`，使用 `PageParams` + `PaginatedListResponse`
- **异常映射**: 所有域异常继承 `HttpMappableDomainError`，由中间件统一映射为 HTTP 响应

### 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Uvicorn |
| LLM 网关 | LiteLLM (OpenAI + Anthropic 协议) |
| Agent 框架 | LangChain + LangGraph |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| 缓存 | Redis |
| 向量库 | Qdrant / Chroma |
| 前端 | React 18 + TypeScript + Vite |
| UI | Tailwind CSS + shadcn/ui + Radix UI |
| 状态管理 | Zustand + TanStack Query |
| 包管理 | uv (后端) / npm (前端) |
| 部署 | Docker Compose + 阿里云 K8s |
