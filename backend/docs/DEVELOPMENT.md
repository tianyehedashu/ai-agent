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
make dev
```

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
uv run uvicorn app.main:app --reload
```

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

```
backend/
├── api/          # API 路由层
├── app/          # 应用核心
├── core/         # 核心类型定义
├── models/       # 数据模型
├── schemas/      # 请求/响应 Schema
├── services/     # 业务服务
├── db/           # 数据库
├── tools/        # Agent 工具
└── tests/        # 测试
```

## 相关文档

- [代码规范](./CODE_STANDARDS.md) - 详细的代码规范说明
- [API 文档](http://localhost:8000/docs) - 启动服务后访问
- [系统架构](../AI-Agent系统架构设计文档.md) - 系统设计文档
