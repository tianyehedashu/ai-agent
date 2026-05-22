# 🚀 开发者快速入门

## 环境要求

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

## 快速开始

### 1. 安装依赖

项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖，提供极快的安装速度。

```bash
# 安装 uv (如果未安装)
# Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# 或者: winget install astral-sh.uv

# Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装开发依赖
make install-all
# 这会执行: uv venv && uv pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库等
```

### 3. 启动开发服务器

```bash
make dev          # 与生产 Dockerfile CMD 一致，无热重载
make dev-reload   # 仅改后端代码时用：watchfiles 热重载
```

## Windows 原生开发提示

> **强烈建议** 在 WSL2 / Devcontainer / Docker 中开发：环境与生产 Docker 一致，
> 自动避开 Windows 原生的若干异步 I/O 兼容性问题（不仅是本节描述的 psycopg
> ProactorEventLoop，还有 watchfiles、文件路径大小写、CRLF 等）。
> Cursor 通过 Remote-WSL 体验与本地几乎无差。

如果坚持 Windows 原生跑后端，请**只通过 `make dev` / `make dev-reload` 启动**，
不要直接调 `uv run uvicorn bootstrap.main:app`。原因：

- uvicorn ≥ 0.40 通过 `asyncio.Runner(loop_factory=...)` 创建事件循环，**完全
  绕过** `asyncio.set_event_loop_policy()`，Windows 默认得到 `ProactorEventLoop`。
- `psycopg` 异步连接（langgraph `AsyncPostgresSaver` 依赖）不支持 ProactorEventLoop，
  会抛 `psycopg.InterfaceError`，导致 checkpointer 回落 MemorySaver（dev 期看不到
  错误但生产语义已经偏离）。
- `scripts/run_server.py` 与 `scripts/run_dev_server.py` 在 Windows 上自动给
  `uvicorn.run` 传 `loop="bootstrap.event_loop:selector_event_loop_factory"`，
  通过 uvicorn 官方扩展点（`Config.get_loop_factory` 的 `import_from_string`
  分支）注入 `SelectorEventLoop` 工厂。**生产 Linux 路径完全不受影响**。
- 机制与设计取舍详见 [`bootstrap/event_loop.py`](../bootstrap/event_loop.py)
  模块 docstring。

### 端口残留排查

`make dev` 异常退出后 uvicorn 进程可能仍占着 8000：

```powershell
netstat -ano | findstr ":8000"
taskkill /PID <PID> /F
```

`make dev-reload`（`scripts/run_dev_server.py`）启动前会自动探测端口，
占用时给出可执行的修复指引。

## 常用命令

所有命令都通过 `uv` 在虚拟环境中执行，无需手动激活虚拟环境。

```bash
# 依赖管理
make install-all    # 创建虚拟环境并安装所有依赖
make sync           # 同步依赖 (从 pyproject.toml 和 uv.lock)
make lock           # 生成/更新 uv.lock 文件

# 代码检查
make check          # 运行所有检查 (格式 + Lint + 类型)
make lint           # 只运行 Ruff 检查
make typecheck      # 只运行类型检查

# 自动修复
make fix            # 自动修复代码问题

# 测试
make test           # 运行测试
make test-cov       # 运行测试并生成覆盖率报告

# 数据库
make db-migrate msg="Add user table"  # 创建迁移
make db-upgrade     # 升级到最新
make db-downgrade   # 回滚一个版本

# 清理
make clean          # 清理临时文件
```

### 直接使用 uv 命令

如果需要直接使用 `uv` 命令：

```bash
# 运行任意命令
uv run <command>    # 在虚拟环境中运行命令

# 示例
uv run pytest
uv run ruff check .
uv run python scripts/run_server.py        # 等价于 make dev
uv run python scripts/run_dev_server.py    # 等价于 make dev-reload
```

> ⚠️ 不要写成 `uv run uvicorn bootstrap.main:app ...`：Windows 上会拿到
> `ProactorEventLoop`，参见上面 [Windows 原生开发提示](#windows-原生开发提示)。

## 提交代码

项目使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```bash
# 格式
<type>(<scope>): <subject>

# 示例
feat(agent): 添加检查点功能
fix(api): 修复会话创建失败问题
docs: 更新 API 文档
```

类型说明:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档
- `style`: 格式调整
- `refactor`: 重构
- `test`: 测试
- `chore`: 杂项

## 质量检查

提交前会自动运行 pre-commit hooks：

```bash
# 手动运行
pre-commit run --all-files
```

## 项目结构

现行后端以 **`domains/` + `bootstrap/` + `libs/`** 为主（与根目录 `AGENTS.md` 一致），勿对照旧版 `api/`、`core/`、`services/` 树。

```
backend/
├── bootstrap/     # FastAPI 入口、路由挂载、生命周期
├── domains/       # 业务域：identity, session, tenancy, agent, gateway, evaluation
├── libs/          # 数据库、配置、中间件、可观测性等非业务基础设施
├── alembic/
├── utils/
└── tests/
```

详见 [ARCHITECTURE.md](./ARCHITECTURE.md) 与 [CODE_STANDARDS.md](./CODE_STANDARDS.md)。

## 相关文档

- [代码规范](./CODE_STANDARDS.md) — 代码与 DDD 分层约定
- [后端架构](./ARCHITECTURE.md) — 现行目录与模块索引
- [API 文档](http://localhost:8000/docs) — 启动服务后访问
- 根目录 `AI-Agent系统架构设计文档.md` 等为产品/需求向历史材料，**实现以 `domains/` 代码为准**
