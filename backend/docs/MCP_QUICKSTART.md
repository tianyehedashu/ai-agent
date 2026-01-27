# MCP 工具管理系统 - 快速开始

## ✅ 实现状态

- **后端**: 11 个新文件 + 4 个修改 (~1,800 行代码)
- **前端**: 4 个新文件 + 2 个修改 (~600 行代码)
- **API 端点**: 6 个 MCP 管理端点
- **数据库**: ✅ 迁移已创建（无外键约束）
- **默认数据**: ✅ 5 个系统级 MCP 服务器预设
- **测试**: ✅ 集成测试 + 权限测试已添加
- **验证**: ✅ 后端导入成功，前端构建成功

---

## 🚀 快速开始

### 1. 启动后端

```bash
cd backend
alembic upgrade head  # 运行迁移，创建 mcp_servers 表并添加默认系统服务器
python -m uvicorn bootstrap.main:app --reload
```

验证: 访问 http://localhost:8000/docs 看到 `/api/v1/mcp/*` 端点

**数据库迁移说明**:
- ✅ **无外键约束**: MCP 服务器表不使用数据库外键，仅通过应用层权限控制
- ✅ **默认系统服务器**: 迁移会自动添加 5 个系统级 MCP 服务器：
  1. `filesystem` - 文件系统访问（默认启用）
  2. `github` - GitHub 集成（需要配置 token）
  3. `postgres` - PostgreSQL 数据库（需要配置连接字符串）
  4. `slack` - Slack 集成（需要配置 token）
  5. `brave-search` - Brave 网页搜索（默认启用）

### 2. 启动前端

```bash
cd frontend
npm install  # 首次运行
npm run dev
```

验证: 访问 http://localhost:5173

### 3. 使用功能

**设置页面**（添加 MCP 服务器）:
1. 访问设置 → "MCP 工具" 标签
2. 点击 "添加服务器"
3. 从模板选择（如 "文件系统"）
4. 点击添加

**对话页面**（配置 MCP 工具）:
1. 创建新对话
2. 点击右上角 ⚙️ 图标
3. 启用需要的 MCP 工具
4. 开始对话

---

## 📁 新增文件

### 后端 (12 个)
```
backend/domains/agent/
├── domain/config/
│   ├── mcp_config.py                    # 类型定义
│   └── templates/__init__.py            # 5 个内置模板
├── infrastructure/
│   ├── models/mcp_server.py             # ORM 模型（无外键）
│   ├── repositories/mcp_server_repository.py
│   └── tools/mcp/
│       ├── wrapper.py                   # 工具包装器
│       └── tool_service.py              # MCP 工具服务
├── application/mcp_use_case.py          # 业务逻辑
└── presentation/
    ├── schemas/mcp_schemas.py
    └── mcp_router.py                    # API 路由

backend/alembic/versions/
└── 20260127_150000_add_mcp_servers.py   # 数据库迁移（无外键 + 默认数据）

backend/tests/integration/api/
└── test_mcp_api.py                      # 集成测试 + 权限测试
```

### 前端 (4 个)
```
frontend/src/
├── types/mcp.ts                         # TypeScript 类型
├── api/mcp.ts                           # API 客户端
└── pages/
    ├── settings/components/mcp-tab.tsx
    └── chat/components/mcp-session-config.tsx
```

---

## 🎯 核心功能

1. **MCP 服务器管理**: 查看、添加、编辑、删除、启用/禁用
2. **模板系统**: 5 个预置模板（filesystem, github, postgres, slack, brave-search）
3. **两级权限**: System 级 + User 级
4. **Session 配置**: 每个对话独立选择 MCP 工具
5. **自动加载**: Agent 对话时自动加载配置的工具

---

## 📊 API 端点

```
GET    /api/v1/mcp/templates                    # 列出模板
GET    /api/v1/mcp/servers                      # 列出服务器
POST   /api/v1/mcp/servers                      # 添加服务器
PUT    /api/v1/mcp/servers/{id}                 # 更新服务器
DELETE /api/v1/mcp/servers/{id}                 # 删除服务器
PATCH  /api/v1/mcp/servers/{id}/toggle          # 切换状态
POST   /api/v1/mcp/servers/{id}/test            # 测试连接
```

---

## 🧪 测试

### 运行集成测试

```bash
cd backend
pytest tests/integration/api/test_mcp_api.py -v
```

**测试覆盖**:

#### 基础功能测试 (TestMCPTemplatesAPI + TestMCPServersAPI)
- ✅ 模板列表 API
- ✅ 服务器 CRUD 操作（创建、读取、更新、删除）
- ✅ 权限验证（认证检查）
- ✅ 边界情况（重名、权限不足等）
- ✅ 状态切换（启用/禁用）
- ✅ 连接测试

#### 权限测试 (TestMCPPermissionsAPI)
- ✅ 用户只能看到自己创建的用户级服务器
- ✅ 用户不能删除/更新系统级服务器
- ✅ 创建用户级服务器时正确设置 user_id
- ✅ 系统级服务器对所有用户可见
- ✅ 用户只能删除自己创建的服务器
- ✅ 系统级服务器 scope 为 "system"，user_id 为 NULL
- ✅ 用户级服务器 scope 为 "user"，user_id 为当前用户 ID

### 测试命令

```bash
# 运行所有 MCP 测试
pytest tests/integration/api/test_mcp_api.py -v

# 运行特定测试类
pytest tests/integration/api/test_mcp_api.py::TestMCPTemplatesAPI -v
pytest tests/integration/api/test_mcp_api.py::TestMCPServersAPI -v
pytest tests/integration/api/test_mcp_api.py::TestMCPPermissionsAPI -v

# 查看测试覆盖率
pytest tests/integration/api/test_mcp_api.py --cov=domains.agent.application.mcp_use_case --cov-report=term
```

---

## ⚠️ 已知限制

1. **MCP 连接测试**: 返回模拟数据
2. **环境配置**: 前端表单简化
3. **批量操作**: 不支持

详细设计: `backend/docs/plans/2025-01-27-mcp-management-*.md`
