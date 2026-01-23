# 开发环境启动指南

本文档说明如何启动 AI Agent 项目的开发环境。

## 前置要求

### 必需工具

- **Python 3.11+** - 后端开发
- **Node.js 18+** - 前端开发
- **Docker & Docker Compose** - 基础服务（PostgreSQL, Redis, Qdrant）
- **uv** - Python 包管理器（推荐，比 pip 快 10-100 倍）
- **make** - 统一命令管理（Windows 需要安装）

### 安装工具

#### Windows

```powershell
# 安装 uv
winget install astral-sh.uv

# 安装 make（如果未安装）
winget install ezwinports.make
```

#### macOS

```bash
# 安装 uv
brew install uv

# 安装 make（通常已预装）
```

#### Linux

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 make
sudo apt install make
```

## 快速启动（推荐）

### 方式一：使用 Docker Compose（最简单）

一键启动所有服务（包括前后端）：

```bash
# 在项目根目录
docker-compose up
```

这将启动：
- ✅ PostgreSQL (localhost:5432)
- ✅ Redis (localhost:6379)
- ✅ Qdrant (localhost:6333)
- ✅ Backend API (localhost:8000)
- ✅ Frontend (localhost:3000)

### 方式二：本地开发（推荐用于开发）

#### 1. 启动基础服务（数据库、缓存、向量数据库）

```bash
# 在项目根目录
make docker-services
# 或手动执行:
docker-compose up -d db redis qdrant
```

等待服务就绪（约 10-30 秒），可通过以下命令检查：

```bash
make docker-ps
```

#### 2. 安装依赖

```bash
# 安装所有依赖（后端 + 前端）
make install

# 或分别安装:
make install-backend  # 后端依赖
make install-frontend # 前端依赖
```

#### 3. 配置环境变量

```bash
# 后端环境变量
cd backend
cp ../env.example .env
# 编辑 .env 文件，配置数据库连接、API 密钥等
```

关键环境变量：

```env
# 数据库（使用 Docker 服务）
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333

# LLM API Keys（必需）
OPENAI_API_KEY=sk-xxx
# 或其他提供商...
```

#### 4. 数据库迁移

```bash
cd backend
make db-upgrade
```

#### 5. 启动开发服务器

**需要两个终端窗口：**

**终端 1 - 后端：**
```bash
cd backend
make dev
```

**终端 2 - 前端：**
```bash
cd frontend
npm run dev
# 或使用 make:
make dev-frontend
```

#### 6. 访问应用

- 🌐 **前端**: http://localhost:3000
- 🔧 **后端 API**: http://localhost:8000
- 📚 **API 文档**: http://localhost:8000/docs

## 详细步骤说明

### 后端启动

#### 1. 安装后端依赖

```bash
cd backend

# 使用 uv 同步依赖（推荐）
make sync
# 或
uv sync --all-extras
```

#### 2. 配置环境变量

创建 `backend/.env` 文件：

```env
APP_ENV=development
DEBUG=true

# 数据库（Docker 服务）
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333

# JWT
JWT_SECRET=dev-secret-key-change-in-production

# LLM API Keys
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
# 其他提供商...
```

#### 3. 数据库迁移

```bash
# 升级到最新版本
make db-upgrade

# 如果需要创建新迁移
make db-migrate msg="your_migration_name"
```

#### 4. 启动开发服务器

```bash
make dev
```

后端将在 http://localhost:8000 启动，支持热重载。

### 前端启动

#### 1. 安装前端依赖

```bash
cd frontend
npm install
# 或使用 npm ci（推荐用于 CI/CD）
npm ci
```

#### 2. 配置环境变量（可选）

创建 `frontend/.env` 文件（如果需要自定义 API 地址）：

```env
VITE_API_URL=http://localhost:8000
```

#### 3. 启动开发服务器

```bash
npm run dev
```

前端将在 http://localhost:3000 启动，支持热重载。

## 常用命令

### 项目根目录（统一管理）

```bash
# 查看所有可用命令
make help

# 安装依赖
make install              # 安装所有依赖
make install-backend      # 只安装后端
make install-frontend     # 只安装前端

# 启动开发服务器
make dev-backend          # 只启动后端
make dev-frontend         # 只启动前端

# Docker 服务管理
make docker-services      # 启动基础服务（db, redis, qdrant）
make docker-up            # 启动所有服务
make docker-down          # 停止所有服务
make docker-logs          # 查看日志
make docker-ps            # 查看运行状态

# 测试
make test                 # 运行所有测试
make test-backend         # 只运行后端测试
make test-frontend        # 只运行前端测试

# 代码质量
make check                # 运行所有检查
make check-backend        # 只检查后端
make check-frontend       # 只检查前端
```

### 后端目录

```bash
cd backend

# 开发
make dev                  # 启动开发服务器
make dev-debug            # 调试模式

# 依赖管理
make sync                 # 同步依赖
make install-all          # 安装所有依赖（包含开发依赖）

# 数据库
make db-upgrade           # 升级数据库
make db-migrate msg="xxx" # 创建迁移
make db-downgrade         # 回滚数据库

# 测试
make test                 # 运行测试（不含 E2E）
make test-all            # 运行所有测试（包含 E2E）
make test-e2e            # 只运行 E2E 测试
make test-cov            # 测试覆盖率

# 代码质量
make lint                 # 代码检查
make format               # 格式化
make typecheck            # 类型检查
make check                # 运行所有检查
make fix                  # 自动修复问题
```

### 前端目录

```bash
cd frontend

# 开发
npm run dev               # 启动开发服务器
npm run build             # 构建生产版本
npm run preview           # 预览生产版本

# 测试
npm run test              # 运行测试
npm run test:ui           # 带 UI 的测试
npm run test:coverage     # 测试覆盖率

# 代码质量
npm run lint              # 代码检查
npm run check             # 运行所有检查
```

## 验证环境

### 检查服务状态

```bash
# 查看 Docker 容器
make docker-ps

# 应该看到以下服务运行中：
# - ai-agent-db (PostgreSQL)
# - ai-agent-redis (Redis)
# - ai-agent-qdrant (Qdrant)
```

### 测试后端 API

```bash
# 健康检查
curl http://localhost:8000/health

# 查看 API 文档
# 浏览器打开: http://localhost:8000/docs
```

### 测试前端

```bash
# 浏览器打开: http://localhost:3000
# 应该能看到应用界面
```

## 常见问题

### 1. 端口被占用

如果端口被占用，可以按以下步骤处理：

#### 检查端口占用

**Windows:**
```powershell
# 检查端口占用
netstat -ano | findstr :6379  # Redis
netstat -ano | findstr :5432  # PostgreSQL
netstat -ano | findstr :6333  # Qdrant
```

**Linux/macOS:**
```bash
lsof -i :6379  # Redis
lsof -i :5432  # PostgreSQL
lsof -i :6333  # Qdrant
```

#### 解决方案

**方案 1: 停止占用端口的容器（推荐）**

如果发现是其他 Docker 容器占用了端口：

```bash
# 查看所有容器
docker ps -a

# 停止并删除占用端口的容器
docker stop <container_name>
docker rm <container_name>

# 然后重新启动服务
make docker-services
```

**方案 2: 修改端口映射**

如果无法停止占用端口的服务，可以修改 `docker-compose.yml` 中的端口映射：

```yaml
# 例如，将 Redis 端口改为 6380
redis:
  ports:
    - "6380:6379"  # 主机端口:容器端口
```

然后更新环境变量：
```env
REDIS_URL=redis://localhost:6380/0
```

**方案 3: 使用不同的端口**

- **后端端口**: 修改 `backend/app/main.py` 或使用 `--port` 参数
- **前端端口**: 修改 `frontend/vite.config.ts` 或使用 `--port` 参数
- **Docker 服务端口**: 修改 `docker-compose.yml`

### 2. 数据库连接失败

确保：
- Docker 服务已启动：`make docker-services`
- 数据库已就绪：等待 10-30 秒
- 环境变量 `DATABASE_URL` 配置正确

### 3. 依赖安装失败

**后端：**
```bash
# 清理并重新安装
cd backend
rm -rf .venv
make sync
```

**前端：**
```bash
# 清理并重新安装
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### 4. Windows 上 make 命令不可用

安装 make：
```powershell
winget install ezwinports.make
```

或直接使用底层命令（见各目录的 README.md）。

### 5. uv 命令不可用

安装 uv：
```powershell
# Windows
winget install astral-sh.uv

# macOS
brew install uv

# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 开发工作流

### 日常开发

1. **启动基础服务**（一次性）
   ```bash
   make docker-services
   ```

2. **启动开发服务器**（每次开发）
   ```bash
   # 终端 1
   cd backend && make dev
   
   # 终端 2
   cd frontend && npm run dev
   ```

3. **运行测试**（提交前）
   ```bash
   make test
   ```

4. **代码检查**（提交前）
   ```bash
   make check
   ```

### 数据库变更

1. 修改模型（`backend/models/`）
2. 创建迁移：`make db-migrate msg="描述"`
3. 检查迁移文件（`backend/alembic/versions/`）
4. 应用迁移：`make db-upgrade`
5. 测试验证

## 下一步

- 📖 查看 [架构文档](ARCHITECTURE.md)
- 📖 查看 [代码规范](CODE_STANDARDS.md)
- 📖 查看 [API 文档](http://localhost:8000/docs)
- 🧪 运行测试了解功能
- 🔍 查看示例代码

## 获取帮助

- 查看 `make help` 获取所有命令
- 查看各目录的 `README.md`
- 查看项目文档：`backend/docs/` 和 `frontend/docs/`
