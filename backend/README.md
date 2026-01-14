# AI Agent Backend

AI Agent 系统后端服务，基于 FastAPI 构建。

## 技术栈

- **框架**: FastAPI
- **语言**: Python 3.11+
- **数据库**: PostgreSQL + SQLAlchemy 2.0
- **缓存**: Redis
- **向量数据库**: Qdrant
- **任务队列**: Celery
- **LLM 网关**: LiteLLM
- **类型检查**: Pyright
- **代码规范**: Ruff

## 项目结构

```
backend/
├── alembic/              # 数据库迁移
├── api/                  # API 路由
│   └── v1/              # API v1 版本
├── app/                  # 应用配置
├── core/                 # 核心类型定义
├── db/                   # 数据库连接
├── models/               # SQLAlchemy 模型
├── schemas/              # Pydantic schemas
├── services/             # 业务服务
├── tools/                # Agent 工具
├── utils/                # 工具函数
├── workers/              # Celery 任务
└── tests/                # 测试文件
```

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
# uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 运行测试

```bash
make test
make test-cov  # 带覆盖率
# 或者使用 uv:
# uv run pytest
```

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
