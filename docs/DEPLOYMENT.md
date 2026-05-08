# AI Agent 部署与安装指南

## 目录

- [架构概览](#架构概览)
- [环境要求](#环境要求)
- [首次部署](#首次部署)
- [日常部署](#日常部署)
- [部署模式说明](#部署模式说明)
- [配置文件说明](#配置文件说明)
- [性能优化](#性能优化)
- [常见问题](#常见问题)
- [服务管理](#服务管理)

---

## 架构概览

```
┌─────────────────────────────────────────────────┐
│                  服务器 (web01)                   │
│                                                   │
│  ┌───────────┐    ┌───────────┐                  │
│  │  Frontend  │───▶│  Backend  │                  │
│  │  (Nginx)   │    │ (FastAPI) │                  │
│  │  :3000     │    │  :8000    │                  │
│  └───────────┘    └─────┬─────┘                  │
│                         │                         │
│         ┌───────────────┼───────────────┐        │
│         ▼               ▼               ▼        │
│  ┌───────────┐   ┌───────────┐   ┌──────────┐   │
│  │ PostgreSQL │   │   Redis   │   │  Qdrant  │   │
│  │  :5432     │   │  :6379    │   │  :6333   │   │
│  └───────────┘   └───────────┘   └──────────┘   │
│                                                   │
│  所有服务通过 Docker Compose 编排                   │
│  内部通信走 Docker 网络 (ai-agent-network)          │
└─────────────────────────────────────────────────┘
```

| 服务 | 技术栈 | 说明 |
|------|--------|------|
| Frontend | React + Vite + Nginx | SPA 应用，Nginx 反代 API |
| Backend | Python + FastAPI + uv | 4 worker 进程 |
| PostgreSQL | 15-alpine | 主数据库 |
| Redis | 7-alpine | 缓存 + 会话 |
| Qdrant | latest | 向量数据库 |

## 环境要求

### 本地开发机（Windows）

- Git、SSH 客户端
- `tar` 命令（Git Bash 自带）
- PowerShell 5.1+
- SSH 配置好 `web01` 别名（`~/.ssh/config`）

### 远程服务器

- Ubuntu 20.04+
- Docker Engine 24+（含 Docker Compose V2）
- 至少 4GB RAM、20GB 磁盘
- 开放端口：3000（前端）、8000（后端）

## 首次部署

### 1. 初始化远程环境

```bash
make deploy-setup
```

自动完成：安装 Docker、配置 docker-compose 插件。

### 2. 配置环境变量

项目根目录下有两个需要配置的环境文件：

**`.env.production`** — Docker Compose 级别变量：

```ini
# 国内服务器需要配置镜像代理（Docker Hub 拉取加速）
REGISTRY_PREFIX=docker.m.daocloud.io/

# 国内构建加速（apt、PyPI、npm 镜像，显著加速依赖安装）
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
NPM_REGISTRY=https://registry.npmmirror.com

# 端口映射
BACKEND_PORT=8000
FRONTEND_PORT=3000

# 数据库密码（请修改为强密码）
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_strong_password
POSTGRES_DB=ai_agent

# Redis 密码
REDIS_PASSWORD=your_redis_password
```

**`deploy/backend.env.production`** — 后端应用环境变量：

```ini
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://postgres:your_password@db:5432/ai_agent
REDIS_URL=redis://:your_redis_password@redis:6379/0
QDRANT_URL=http://qdrant:6333

# LLM API Keys（按需填写）
DASHSCOPE_API_KEY=...
DEEPSEEK_API_KEY=...
```

> 首次部署时，脚本会自动将 `deploy/backend.env.production` 复制为 `backend/.env`。

### 3. 执行首次部署

```bash
make deploy
```

首次部署耗时较长（约 5-15 分钟），因为需要：
- 下载 Docker 基础镜像
- 安装 Python/Node.js 依赖
- 构建前后端应用

## 日常部署

### 推荐工作流

| 场景 | 命令 | 耗时 |
|------|------|------|
| **代码变更（无依赖变化）** | `make deploy` | ~2-3 分钟 |
| **仅改了配置/少量代码** | `make deploy-quick` | ~1 分钟 |
| **依赖包有更新** | `make deploy` | ~3-5 分钟 |
| **需要完全重建** | `make deploy-rebuild` | ~5-15 分钟 |
| **仅同步代码不重启** | `make deploy-sync` | ~30 秒 |

### 为什么后续部署比首次快？

1. **基础镜像复用**：`ai-agent-backend-base`（含 gcc、uv）首次构建后持久化，后续部署直接复用，无需重复 apt-get 安装 build-essential 等。
2. **Docker 分层缓存**：依赖层与代码层分离，lock 文件未变时跳过依赖安装。

```
┌─────────────────────────────────────────┐
│ Base: ai-agent-backend-base (gcc, uv)   │ ← 构建一次，后续复用
├─────────────────────────────────────────┤
│ Layer 2: 项目依赖 (uv sync / npm ci)    │ ← 仅 lock 文件变化时重建
├─────────────────────────────────────────┤
│ Layer 3: 应用代码 (COPY . .)            │ ← 每次部署更新
└─────────────────────────────────────────┘
```

- **依赖未变** → Base 复用，Layer 2 命中缓存，仅复制代码（秒级）
- **依赖变了** → Layer 2 重建（后端 ~2min，前端 ~1min）
- **`--rebuild`** → 全部重建（`--no-cache`）

## 部署模式说明

### `make deploy` — 标准部署

完整流程：同步代码 → 构建镜像 → 数据库迁移 → 启动服务。

适用于大多数场景，Docker 层缓存会自动跳过未变化的步骤。

### `make deploy-quick` — 快速部署

同步代码 → 直接重启容器（跳过镜像构建）。

适用于仅修改了后端 Python 代码且不需要重建镜像的场景。注意：如果修改了 Dockerfile 或依赖文件，需要用标准部署。

### `make deploy-rebuild` — 强制重建

同步代码 → `--no-cache` 重新构建 → 启动服务。

适用于：Docker 缓存异常、基础镜像需要更新、依赖安装出问题。

### `make deploy-sync` — 仅同步

只上传代码到服务器，不执行任何构建或重启。

适用于：提前准备代码，稍后手动操作。

### 服务器端：`./deploy/deploy.sh --build-base` — 重建基础镜像

仅当升级 Python/uv 版本或需要强制刷新基础镜像时使用。执行后重新构建 `ai-agent-backend-base`（含 gcc、uv），下次 `make deploy` 将使用新镜像。

## 配置文件说明

```
项目根目录/
├── .env.production              # Docker Compose 变量（端口、密码、镜像）
├── .env.production.example      # ↑ 的模板
├── docker-compose.prod.yml      # 生产编排配置
├── deploy/
│   ├── deploy.sh                # 服务器端部署脚本
│   ├── remote-deploy.ps1        # 本地 Windows 部署入口
│   └── backend.env.production   # 后端 .env 模板（含 API Keys）
├── backend/
│   ├── Dockerfile               # 后端镜像（多阶段构建）
│   ├── Dockerfile.base          # 基础镜像（gcc、uv，构建一次复用）
│   ├── .dockerignore            # 排除测试/缓存等无关文件
│   └── .env                     # 运行时环境变量（由模板生成）
└── frontend/
    ├── Dockerfile               # 前端镜像（多阶段构建）
    ├── .dockerignore            # 排除 node_modules/dist 等
    └── nginx.conf               # Nginx 配置（API 反代 + SPA）
```

## 性能优化

已实施的优化措施：

| 优化项 | 效果 |
|--------|------|
| **基础镜像复用** | gcc、uv 等系统依赖构建一次，后续复用，避免重复 apt-get |
| **国内镜像** | apt、PyPI、npm 使用清华/npmmirror 镜像，国内构建加速 |
| `.dockerignore` 排除无关文件 | 构建上下文减小 ~60% |
| 多阶段构建 + 层分离 | 依赖未变时构建秒级完成 |
| 并行构建前后端 | 构建时间减少 ~40% |
| 基础设施服务智能跳过 | 已运行的 DB/Redis 不重复启动 |
| 生产镜像最小化 | 后端不含 build-essential，前端仅 Nginx + 静态文件 |
| 日志轮转 | 防止磁盘被日志撑满 |
| 资源限制 | 防止单个服务占用过多资源 |

## 常见问题

### Q: Docker 镜像拉取失败（国内网络）

配置 `.env.production` 中的 `REGISTRY_PREFIX`：

```ini
REGISTRY_PREFIX=docker.m.daocloud.io/
```

### Q: 构建时 apt/pip/npm 下载很慢

配置 `.env.production` 中的国内镜像（apt 已内置清华源，以下为 PyPI、npm）：

```ini
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
NPM_REGISTRY=https://registry.npmmirror.com
```

### Q: 权限不足 `permission denied while trying to connect to the Docker daemon`

```bash
sudo usermod -aG docker $USER
# 重新登录或使用 sg docker
sg docker -c "bash deploy/deploy.sh"
```

部署脚本已内置自动 `sg docker` 处理。

### Q: 数据库迁移失败

```bash
# 查看迁移状态
ssh web01 "cd ~/ai-agent && docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backend alembic current"

# 手动迁移
ssh web01 "cd ~/ai-agent && docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backend alembic upgrade head"
```

### Q: 本地执行 docker compose build 失败（找不到 ai-agent-backend-base）

生产镜像依赖预构建的基础镜像。本地构建前需先执行：

```bash
docker build -f backend/Dockerfile.base -t ai-agent-backend-base:latest backend/
```

或通过远程部署（会自动构建）：`make deploy`。

### Q: 前端构建失败（TypeScript 错误）

本地先验证：

```bash
cd frontend && npm run build
```

### Q: 如何查看某个服务的日志？

```bash
# 所有日志
make deploy-logs

# 单个服务
ssh web01 "cd ~/ai-agent && docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend"
```

### Q: 如何回滚？

目前采用代码级回滚：

```bash
# 本地回退到上一个版本
git checkout <commit-hash>

# 重新部署
make deploy
```

## 服务管理

### 本地命令（通过 Makefile）

```bash
make deploy-status    # 查看服务状态
make deploy-logs      # 查看日志（实时）
make deploy-stop      # 停止所有服务
```

### 服务器端直接操作

```bash
ssh web01
cd ~/ai-agent

# 使用 deploy.sh
./deploy/deploy.sh --status
./deploy/deploy.sh --logs
./deploy/deploy.sh --restart
./deploy/deploy.sh --stop

# 或直接使用 docker compose
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend
docker compose -f docker-compose.prod.yml --env-file .env.production restart backend
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://192.168.26.90:3000 |
| 后端 API | http://192.168.26.90:8000 |
| API 文档 | http://192.168.26.90:8000/docs |
