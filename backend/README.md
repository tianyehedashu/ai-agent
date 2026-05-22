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
│   ├── gateway/          # AI Gateway、OpenAI/Anthropic 对外入口、团队/预算/日志
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

### Listing Studio / Chat 默认模型

对话与 **Listing Studio**（`/api/v1/listing-studio`）步骤执行依赖 **Gateway 可见模型目录**，而非 `app.toml` 中的静态默认 ID：

1. 在 Gateway 配置 Provider **凭据**（`/gateway/credentials`）
2. 同步目录：`POST /api/v1/gateway/catalog/reload-from-config`（或管理面等价操作）
3. 确认目标模型在 `list_visible_models` 中且类型匹配（text / image / image_gen）

无可见模型时 API 返回 `ValidationError`，前端 ModelSelector 显示「暂无可用模型」。旧 API 路径 `/api/v1/product-info` 已弃用，请迁移至 `/api/v1/listing-studio`。

### Listing Studio 对象存储

用户上传与 8 图生成结果统一走 **PostgreSQL `system_storage_config`** 配置，**不依赖** `.env` 中的 `STORAGE_TYPE` / `S3_*`（这些 Settings 字段已废弃）。

1. 以平台管理员登录，打开 **对象存储**（`/admin/storage`）或调用 `GET/PUT /api/v1/admin/storage`
2. **开发**：默认 `local`，图片落在 `./data/storage/images`，通过 `/api/v1/listing-studio/images/{filename}` 访问
3. **生产（Cloudflare R2）**：
   - `storage_type`: `s3`
   - `s3_endpoint_url`: `https://<account_id>.r2.cloudflarestorage.com`
   - `s3_region`: `auto`
   - `s3_public_base_url`: R2.dev 子域或自定义 CDN 前缀（bucket 需开启公开读）
4. **阿里云 OSS**：同上，endpoint 填 `https://oss-cn-<region>.aliyuncs.com`

保存后点击 **测试连接** 验证；切换 bucket/endpoint 后新上传走新配置，历史 URL 无需立即迁移。

### Gateway PII 守卫（默认关闭）

出站 `/v1/*` 代理可在 LiteLLM `pre_call_hook` 中对消息做手机/邮箱/身份证/银行卡/IPv4 脱敏。**默认不启用**：

1. 部署：`GATEWAY_DEFAULT_GUARDRAIL_ENABLED=false`（见仓库根 `env.example`）
2. 开放后设为 `true`，并在控制台为虚拟 Key 开启「PII 守卫」（`guardrail_enabled`）
3. 两层开关：**全局** 控制是否注册回调；**单次请求** 的 `metadata.guardrail_enabled` 来自 vkey/grant，二者同时为真才脱敏

详见 [docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md](docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md) §6.2。

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

本地与 CI 使用 `alembic upgrade`（`alembic/versions/*.py`）。**生产**由运维按链手工执行 `alembic/sql/<与 versions 同名>.up.sql`（升级）/ `.down.sql`（回滚），Alembic **不会**加载这些文件；含义与命名见 `alembic/sql/README.md`。可用 `scripts/generate_alembic_sql_files.py` 从 Python 迁移重新导出运维脚本。

### 运行开发服务器

```bash
make dev          # 与生产 Dockerfile CMD 一致，无热重载
make dev-reload   # 仅改后端代码时用：watchfiles 热重载
```

> **Windows 原生开发请勿直接调 `uv run uvicorn bootstrap.main:app`**：
> uvicorn ≥ 0.40 默认创建 `ProactorEventLoop`，会让 psycopg / langgraph
> `AsyncPostgresSaver` 抛 `InterfaceError` 并悄悄回落 MemorySaver。`make dev`
> 经 `scripts/run_server.py` 自动注入 `SelectorEventLoop` 工厂。
> 详见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#windows-原生开发提示) 与
> [`bootstrap/event_loop.py`](bootstrap/event_loop.py)。
> **更推荐 WSL2 / Devcontainer / Docker dev** 一次性避开此类 Windows-only 问题。

### 运行测试

```bash
make test
make test-cov  # 带覆盖率
# 或者使用 uv:
# uv run pytest
```

## 架构文档（节选）

- [AI Gateway 领域架构与工程实践](docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md) — `domains/gateway` 分层、认证、数据要点、测试与前后端契约
- [Claude Code / Cursor 适配说明](docs/GATEWAY_CURSOR_CLAUDE_CODE.md) — 能力清单、模型别名、架构落点、排错与 SOP
- [第三方协议客户端接入指南](docs/GATEWAY_THIRDPARTY_CLIENT_GUIDE.md) — 速查配置（Claude Code / Cursor / SDK）
- [Gateway 生产部署清单](docs/GATEWAY_DEPLOYMENT_CHECKLIST.md) — SSE、长连接、nginx/uvicorn
- [LLM Gateway 架构设计说明](docs/LLM_GATEWAY_ARCHITECTURE.md) — LiteLLM 选型与本项目 Gateway 抽象

## API 文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### AI Gateway 对外协议（`/api/v1/openai|anthropic`）

同一服务下提供两套 HTTP 面（可选服务级前缀 `ROOT_PATH`，如 `/ai-agent`）。虚拟 Key（`sk-gw-...`）与带 `gateway:proxy` 且命中 Gateway grant 的 API Key 均可使用；鉴权支持 **`Authorization: Bearer <token>`** 或 **`x-api-key: <token>`**（同时存在时优先 Bearer）。`X-Team-Id` 在使用业务 `sk-` 时只用于选择该 Key 已授权的团队。

| 协议 | SDK base_url | 示例端点 |
|------|--------------|----------|
| OpenAI 兼容 | `{ROOT}/api/v1/openai/v1` | `POST .../chat/completions`、`GET .../models` |
| Anthropic Messages | `{ROOT}/api/v1/anthropic` | `POST .../v1/messages` |

Anthropic 请求体中的 `model` 须与网关注册 / 路由中的模型名一致（可与 OpenAI 面共用白名单与预算维度）。

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
