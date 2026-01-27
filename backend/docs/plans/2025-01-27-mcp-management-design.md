# MCP 工具管理系统设计方案

**日期**: 2025-01-27
**版本**: 1.0
**状态**: 设计完成，待实施

---

## 1. 概述

### 1.1 目标

构建完整的 MCP (Model Context Protocol) 工具管理系统，实现：

- **两级隔离**：系统预置 + 用户自定义
- **会话级配置**：每个 Session 可选择启用的 MCP 工具
- **模板化配置**：提供常用 MCP 服务器模板，降低配置门槛
- **环境适配**：支持多种 MCP 工具环境配置方式

### 1.2 核心功能

1. **MCP 服务器管理**
   - 查看、添加、编辑、删除 MCP 服务器
   - 启用/禁用服务器
   - 测试连接和健康检查

2. **模板系统**
   - 预置常用 MCP 服务器模板（GitHub、Filesystem、PostgreSQL 等）
   - 快速配置（填写少量参数即可）

3. **Session 集成**
   - 从可用工具池选择 MCP 工具
   - Agent 对话时使用启用的 MCP 工具

4. **权限控制**
   - 系统服务器：所有人可见，仅管理员可修改
   - 用户服务器：仅创建者可见和操作

---

## 2. 架构设计

### 2.1 两级隔离模型

```
┌─────────────────────────────────────────────┐
│         系统预置 MCP 服务器                  │
│   (scope=system, user_id=NULL)             │
│   - 管理员配置                               │
│   - 所有用户可见                             │
│   - 管理员可修改                             │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         用户可用工具池                       │
│   = system 服务器 ∪ user 自己的服务器        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Session 选择启用                     │
│   mcp_config.enabled_servers = [...]        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         ConfiguredMCPManager                │
│   仅加载 Session 启用的服务器                │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         Agent 可以调用工具                   │
└─────────────────────────────────────────────┘
```

### 2.2 分层架构

#### Domain 层

**类型定义**：
- `MCPServerConfig` - MCP 服务器配置实体
- `MCPEnvironmentType` - 环境类型枚举（dynamic_injected / preinstalled / custom_image）
- `MCPScope` - 作用域枚举（system / user）
- `MCPTemplate` - MCP 服务器模板

#### Application 层

**UseCase**：
- `MCPManagementUseCase` - MCP 管理业务逻辑
  - `list_servers()` - 列出可用服务器
  - `add_server()` - 添加用户级服务器
  - `update_server()` - 更新服务器（带权限检查）
  - `delete_server()` - 删除服务器（带权限检查）
  - `test_connection()` - 测试连接
  - `list_templates()` - 列出模板

#### Infrastructure 层

**Repository**：
- `MCPServerRepository` - 继承 `OwnedRepositoryBase`
  - 自动权限过滤（利用 `PermissionContext`）
  - `_apply_mcp_scope_filter()` - MCP 特定过滤逻辑
  - `list_available()` - 返回 (system, user) 元组

**模型**：
- `MCPServer` - SQLAlchemy 模型
  - 字段：id, name, display_name, description, url, scope, user_id, env_type, env_config, api_key_env, enabled, auto_start

**MCP 客户端**：
- `MCPClient` - 连接和调用 MCP 服务器
- `ConfiguredMCPManager` - 管理多个 MCP 客户端

#### Presentation 层

**路由**：
- `GET /api/mcp/templates` - 获取模板列表
- `GET /api/mcp/servers` - 获取服务器列表
- `POST /api/mcp/servers` - 添加服务器
- `PUT /api/mcp/servers/{id}` - 更新服务器
- `DELETE /api/mcp/servers/{id}` - 删除服务器
- `POST /api/mcp/servers/{id}/test` - 测试连接
- `PATCH /api/mcp/servers/{id}/toggle` - 启用/禁用

**Session 扩展**：
- `GET /api/sessions/{id}/mcp-config` - 获取 Session MCP 配置
- `PUT /api/sessions/{id}/mcp-config` - 更新 Session MCP 配置

---

## 3. 数据模型

### 3.1 数据库表

**mcp_servers 表**：

```sql
CREATE TABLE mcp_servers (
    id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    url VARCHAR(500) NOT NULL,
    scope VARCHAR(20) NOT NULL,          -- 'system' | 'user'
    user_id UUID,                         -- NULL for system servers

    env_type VARCHAR(50) NOT NULL,        -- 'dynamic_injected' | 'preinstalled' | 'custom_image'
    env_config JSONB NOT NULL DEFAULT '{}',
    api_key_env VARCHAR(100),

    enabled BOOLEAN DEFAULT TRUE,
    auto_start BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT mcp_servers_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_mcp_servers_scope_user ON mcp_servers(scope, user_id);
```

**sessions 表扩展**：

```sql
ALTER TABLE sessions
ADD COLUMN mcp_config JSONB DEFAULT '{}';
-- 示例：{"enabled_servers": ["filesystem", "github"]}
```

### 3.2 Pydantic 模型

```python
class MCPServerConfig(BaseModel):
    id: UUID | None = None
    name: str
    display_name: str | None = None
    description: str | None = None
    url: str
    scope: MCPScope
    user_id: UUID | None = None

    env_type: MCPEnvironmentType
    env_config: dict[str, Any] = {}
    api_key_env: str | None = None

    enabled: bool = True
    auto_start: bool = False

class MCPTemplate(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    category: str
    icon: str | None = None

    default_config: MCPServerConfig
    required_fields: list[str]
    optional_fields: list[str]

    field_labels: dict[str, str]
    field_placeholders: dict[str, str]
    field_help_texts: dict[str, str]
```

---

## 4. 权限控制

### 4.1 两层权限检查

**粗粒度（Presentation 层）**：
- `RequiredAuthUser` - 必须认证
- `AdminUser` - 必须是管理员（修改 system 服务器）

**细粒度（Repository 层）**：
- `OwnedRepositoryBase` - 自动所有权过滤
- `_apply_mcp_scope_filter()` - MCP 特定逻辑（所有人可见 system 服务器）

### 4.2 权限规则

| 操作 | System 服务器 | User 服务器 |
|------|---------------|-------------|
| 查看 | 所有人 | 所有者 |
| 添加 | 仅管理员 | 认证用户（强制为 user） |
| 修改 | 仅管理员 | 所有者 |
| 删除 | 仅管理员 | 所有者 |
| 启用/禁用 | 所有人 | 所有者 |

---

## 5. 模板系统

### 5.1 预置模板

**GitHub**：
- 描述：GitHub 仓库操作、Issue 管理、PR 审查
- 环境类型：preinstalled（Node.js）
- 必填：api_token
- 可选：repositories

**Filesystem**：
- 描述：读写本地文件系统（在沙箱中运行）
- 环境类型：preinstalled（Python）
- 可选：allowed_roots

**PostgreSQL**：
- 描述：数据库查询和管理
- 环境类型：dynamic_injected
- 必填：connection_string

**Slack**：
- 描述：发送消息、读取频道、管理用户
- 环境类型：dynamic_injected
- 必填：bot_token

**Brave Search**：
- 描述：网页搜索和内容获取
- 环境类型：dynamic_injected
- 必填：api_key

### 5.2 模板配置流程

```
1. 用户选择模板
   ↓
2. 显示必填字段表单（动态生成）
   ↓
3. 用户填写参数
   ↓
4. 创建 MCPServerConfig（scope 强制为 user）
   ↓
5. 保存到数据库
```

---

## 6. Session 集成

### 6.1 配置流程

```python
# 1. 获取可用的服务器列表
available = await mcp_use_case.list_servers()
# → {system_servers: [...], user_servers: [...]}

# 2. 用户选择启用的服务器
session.mcp_config = {"enabled_servers": ["filesystem", "github"]}

# 3. Agent 执行时加载
enabled_names = session.mcp_config.get("enabled_servers", [])
mcp_manager = ConfiguredMCPManager(config)  # 仅加载启用的
await mcp_manager.initialize()

# 4. 注册工具到 ToolRegistry
tools = await mcp_manager.list_all_tools()
for tool in tools:
    tool_registry.register(wrap_mcp_tool(tool))
```

### 6.2 工具命名空间

MCP 工具使用命名空间隔离：
- 格式：`{server_name}.{tool_name}`
- 示例：`github.create_issue`, `filesystem.read_file`

---

## 7. 错误处理

### 7.1 异常类型

- `MCPConnectionError` - 连接失败
- `MCPToolExecutionError` - 工具执行失败

### 7.2 重试策略

- 连接超时：重试 2 次，间隔 1 秒
- 工具调用失败：不重试，返回错误给 Agent

### 7.3 用户友好错误

| 错误类型 | 用户消息 |
|---------|---------|
| TimeoutError | "连接超时，请检查服务器地址" |
| ConnectionError | "连接失败：{details}" |
| PermissionError | "无权限操作此服务器" |
| NotFound | "服务器不存在" |

---

## 8. 前端设计

### 8.1 页面结构

**设置页面**：新增 "MCP 工具" 标签页
- 系统服务器列表（只读，可启用/禁用）
- 用户服务器列表（可编辑、删除）
- 添加服务器按钮（模板 / 自定义）

**对话页面**：新增 MCP 配置面板
- 显示可用的服务器
- 启用/禁用开关
- 显示工具数量

### 8.2 组件

- `MCPServersTab` - 主容器
- `MCPServerList` - 服务器列表
- `MCPServerCard` - 服务器卡片（带健康状态）
- `AddMCPServerDialog` - 添加对话框
- `TemplateSelector` - 模板选择器
- `TemplateConfigForm` - 模板配置表单
- `MCPConfigPanel` - Session 配置面板

---

## 9. 环境配置

### 9.1 三种环境类型

**1. dynamic_injected（动态注入）**
- 适用：需要运行时依赖（Python 包）
- 实现：在沙箱中动态安装
- 示例：`pip install mcp-server-postgres`

**2. preinstalled（预装依赖）**
- 适用：常用工具，预装在基础镜像
- 实现：Dockerfile 中预装
- 示例：`RUN npm install -g @modelcontextprotocol/server-github`

**3. custom_image（自定义镜像）**
- 适用：特殊依赖或隔离需求
- 实现：指定 Docker 镜像
- 示例：`custom-image:latest`

### 9.2 配置示例

```json
{
  "env_type": "dynamic_injected",
  "env_config": {
    "runtime": "python",
    "package": "mcp-server-postgres"
  }
}
```

---

## 10. 测试策略

### 10.1 单元测试

- Repository 层：权限过滤逻辑
- UseCase 层：业务规则验证
- 工具包装：MCP 工具命名空间

### 10.2 集成测试

- API 端点：CRUD 操作
- 权限控制：不同角色的访问权限
- Session 集成：MCP 配置加载

### 10.3 E2E 测试

- 完整流程：配置 → Session → 对话 → 工具调用
- 权限流程：管理员创建系统服务器 → 用户使用

---

## 11. 部署清单

### 11.1 数据库迁移

- 创建 `mcp_servers` 表
- 扩展 `sessions` 表（添加 `mcp_config` 字段）
- 插入系统预置服务器

### 11.2 配置文件

- `config/mcp_servers.toml` - 系统服务器初始化配置
- `.env` - API Key 环境变量

### 11.3 依赖安装

如支持预装 MCP 服务器：
```dockerfile
RUN npm install -g @modelcontextprotocol/server-github
RUN pip install mcp-server-filesystem mcp-server-postgres
```

---

## 12. 后续优化

1. **批量操作**：批量启用/禁用服务器
2. **导入/导出**：导出用户配置，跨实例迁移
3. **监控**：MCP 工具调用统计、性能监控
4. **版本管理**：MCP 服务器配置版本控制
5. **市场**：社区分享 MCP 服务器配置模板

---

## 附录

### A. API 端点清单

详见第 2.2 节 Presentation 层。

### B. 数据库 Schema

详见第 3.1 节。

### C. 权限矩阵

详见第 4.2 节。
