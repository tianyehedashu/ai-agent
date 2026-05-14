# AI Agent 系统

> 一个完整的 AI Agent 开发与运行平台，以对话式 Agent 为核心

## 🎯 项目概述

AI Agent 系统是一个功能完整的 AI Agent 开发和运行平台，包含：

- **Agent Core** - 核心执行引擎，实现 ReAct 模式的 Agent 循环
- **AI Gateway** - OpenAI 与 Anthropic（`/v1/messages`）兼容入口、模型路由、凭证、预算、团队和日志管理
- **MCP 集成** - 系统级 MCP Server 管理与 Streamable HTTP 入口
- **基础设施** - API 网关、数据库、向量库、缓存

## ✨ 核心功能

### Agent Core 引擎
- ✅ Main Loop 执行循环
- ✅ 上下文管理 (Token 预算、滑动窗口)
- ✅ 多模型支持 (OpenAI, Claude via LiteLLM)
- ✅ 工具系统 (文件操作、代码执行、搜索)
- ✅ 检查点系统 (状态保存、恢复)
- ✅ Human-in-the-Loop (敏感操作确认)
- ✅ 终止条件 (迭代次数、Token、超时)

### 记忆系统
- ✅ 向量数据库存储 (Qdrant/Chroma)
- ✅ 多路召回检索
- ✅ 自动记忆提取

## 🛠 技术栈

### 后端
- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 + Alembic
- Redis
- LiteLLM
- Qdrant / Chroma

### 前端
- React 18 + TypeScript
- Vite
- Tailwind CSS + shadcn/ui
- Zustand

## 📁 项目结构

```
ai-agent/
├── backend/                 # 后端服务
│   ├── bootstrap/           # FastAPI 入口、生命周期、路由注册
│   ├── domains/             # 业务域
│   │   ├── identity/        # 身份认证、用户、API Key、权限
│   │   ├── session/         # 会话、标题、会话归属
│   │   ├── agent/           # Agent 对话、工具、记忆、MCP、沙箱、垂直任务
│   │   ├── gateway/         # AI Gateway、OpenAI/Anthropic 入口、团队/预算/日志
│   │   └── evaluation/      # 评估接口
│   ├── libs/                # 纯技术基础设施
│   │   ├── api/             # 服务工厂、通用 API 依赖
│   │   ├── config/          # 配置管理
│   │   ├── db/              # 数据库、Redis、向量库
│   │   ├── middleware/      # 中间件
│   │   └── types/           # 通用工具类型
│   ├── alembic/             # 数据库迁移
│   ├── tests/               # 后端测试
│   └── utils/               # 技术工具函数
│
├── frontend/                # 前端应用
│   └── src/
│       ├── api/             # API 客户端
│       ├── components/      # 组件
│       ├── hooks/           # Hooks
│       ├── pages/           # 页面
│       ├── stores/          # 状态管理
│       └── types/           # 类型定义
│
├── deploy/                  # 部署脚本与配置
├── docs/                    # 项目级文档
├── scripts/                 # 项目级脚本
├── Makefile                 # 前后端统一管理命令
├── docker-compose.yml       # 开发环境
└── docker-compose.prod.yml  # 生产环境
```

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15
- Redis 7

### 1. 克隆项目
```bash
git clone <repository-url>
cd ai-agent
```

### 2. 启动基础服务
```bash
docker-compose up -d db redis qdrant
# 或者:
make docker-services
```

### 3. 后端设置
```bash
cd backend

# 安装所有依赖 (使用 uv + make)
make install-all

# 配置环境变量
cp ../env.example .env
# 编辑 .env 文件，设置必要的配置

# 运行数据库迁移
make db-upgrade

# 启动后端服务
make dev
```

> **注意**: 需要先安装 [uv](https://docs.astral.sh/uv/) 和 [make](https://www.gnu.org/software/make/)
> - Windows: `winget install astral-sh.uv ezwinports.make`
> - macOS: `brew install uv make`
> - Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh && sudo apt install make`

### 4. 前端设置
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 5. 访问应用
- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 🔧 配置说明

### 环境变量

```env
# 应用配置
APP_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key

# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM API Keys
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# 向量数据库
QDRANT_URL=http://localhost:6333

# JWT
JWT_SECRET_KEY=your-jwt-secret
```

## 📚 API 文档

启动后端后访问 http://localhost:8000/docs 查看完整的 API 文档。

### 核心 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/chat` | POST | 发送消息 (SSE) |
| `/api/v1/chat/resume` | POST | 恢复执行 |
| `/api/v1/agents` | CRUD | Agent 管理 |
| `/api/v1/sessions` | CRUD | 会话管理 |
| `/api/v1/mcp` | CRUD | MCP 管理 |
| `/api/v1/gateway/*` | CRUD | AI Gateway 管理 |
| `/v1/*` | 兼容 OpenAI / Anthropic | Chat Completions、Embeddings、Images、Audio、Models；`POST /v1/messages`（Anthropic Messages） |
| `/api/v1/product-info` | CRUD | 产品信息任务 |
| `/api/v1/video-tasks` | CRUD | 视频生成任务 |

## 🧪 测试

### 后端测试
```bash
cd backend
pytest
```

### 前端测试
```bash
cd frontend
npm run test
```

## 🐳 Docker 部署

### 开发环境
```bash
docker-compose up
```

### 生产环境
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 📝 开发指南

### 添加新工具

1. 在 `backend/domains/agent/infrastructure/tools/` 创建工具文件
2. 继承 `BaseTool` 类
3. 使用 `@register_tool` 装饰器注册
4. 在 `backend/domains/agent/infrastructure/tools/__init__.py` 导入模块以触发注册

```python
from domains.agent.domain.types import ToolCategory, ToolResult
from domains.agent.infrastructure.tools.base import BaseTool, register_tool

@register_tool
class MyTool(BaseTool):
    name = "my_tool"
    description = "工具描述"
    category = ToolCategory.SYSTEM

    async def execute(self, tool_call_id: str = "", value: str = "") -> ToolResult:
        # 实现逻辑
        return ToolResult(tool_call_id=tool_call_id, success=True, output=f"结果: {value}")
```

### 添加新 API

1. 在对应业务域的 `presentation/` 创建路由文件
2. 在该业务域的 `application/` 添加用例服务
3. 如需持久化，在该业务域的 `infrastructure/models/` 和 `infrastructure/repositories/` 添加模型与仓储
4. 在 `backend/bootstrap/main.py` 注册路由

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
