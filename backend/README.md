# AI Agent Backend

AI Agent 系统后端服务，基于 FastAPI 构建。

## 技术栈

- **框架**: FastAPI
- **语言**: Python 3.11+
- **数据库**: PostgreSQL + SQLAlchemy 2.0
- **缓存**: Redis
- **向量数据库**: Qdrant
- **后台任务**: FastAPI 应用生命周期 + 应用内后台任务调度
- **LLM 网关**: LiteLLM
- **类型检查**: Pyright
- **代码规范**: Ruff

## 项目结构

```
backend/
├── alembic/              # 数据库迁移
├── bootstrap/            # FastAPI 入口、生命周期、路由注册
├── domains/              # 业务域
│   ├── identity/         # 身份认证、用户、API Key、权限
│   ├── session/          # 会话、标题、会话归属
│   ├── agent/            # Agent 对话、工具、记忆、MCP、沙箱、垂直任务
│   ├── gateway/          # AI Gateway、OpenAI 兼容入口、团队/预算/日志
│   ├── studio/           # 工作台、工作流、代码质量、LSP
│   └── evaluation/       # 评估接口
├── libs/                 # 纯技术基础设施
│   ├── api/              # 服务工厂、通用 API 依赖
│   ├── config/           # 配置管理
│   ├── db/               # 数据库、Redis、向量库
│   ├── middleware/       # 中间件
│   ├── observability/    # 日志、指标、追踪、Sentry
│   └── types/            # 通用工具类型
├── utils/                # 工具函数
├── scripts/              # 维护脚本
└── tests/                # 测试文件
```

**规范与域文档**：仓库根 [AGENTS.md](../AGENTS.md)；后端分层见 [docs/CODE_STANDARDS.md](./docs/CODE_STANDARDS.md)；Gateway 见 [docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md](./docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md)。`docs/DIRECTORY_STRUCTURE_ANALYSIS.md` 为旧版目录归档说明，勿作现行树来源。

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### 安装依赖

项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖，速度比 pip 快 10-100 倍。

```bash
# 安装 uv (如果未安装)
# Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# 或者: winget install astral-sh.uv

# Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
make install-all
# 或者手动执行:
# uv venv
# uv pip install -e ".[dev]"
```

### 配置环境变量

```bash
cp ../env.example .env
# 编辑 .env 文件，填写实际配置
```

### 数据库迁移

```bash
# 生成迁移
make db-migrate msg="initial"
# 或者: uv run alembic revision --autogenerate -m "initial"

# 执行迁移
make db-upgrade
# 或者: uv run alembic upgrade head
```

### 运行开发服务器

```bash
make dev
# 或者使用 uv:
# uv run uvicorn bootstrap.main:app --reload --host 0.0.0.0 --port 8000
```

### 运行测试

```bash
make test
make test-cov  # 带覆盖率
# 或者使用 uv:
# uv run pytest
```

## 架构文档（节选）

- [AI Gateway 领域架构与工程实践](docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md) — `domains/gateway` 分层、认证、数据要点、测试与前后端契约
- [LLM Gateway 架构设计说明](docs/LLM_GATEWAY_ARCHITECTURE.md) — LiteLLM 选型与本项目 Gateway 抽象

## API 文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 核心模块

### Agent 引擎

实现 Agent 的核心执行循环，包括:
- Main Loop: 主执行循环
- Context Manager: 上下文管理
- Tool System: 工具系统
- Memory System: 记忆系统

### 检查点系统

支持 Time Travel Debugging:
- 自动保存执行状态
- 支持回滚到任意检查点
- 检查点差异对比

### HITL (Human-in-the-Loop)

人机协作功能:
- 敏感操作确认
- 参数修改
- 执行中断与恢复

## 开发规范

### 类型检查

```bash
pyright .
```

### 代码格式化

```bash
ruff format .
ruff check . --fix
```

### 提交规范

使用 Conventional Commits 规范:
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 其他
