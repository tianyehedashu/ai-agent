# MCP 服务器自动初始化

## 功能概述

应用启动时会自动检查并初始化默认的系统级 MCP 服务器，确保基础服务始终可用。

## 默认服务器列表

系统会自动创建以下 5 个默认系统级 MCP 服务器：

| 名称 | 显示名称 | 状态 | 说明 |
|------|---------|------|------|
| filesystem | 文件系统 | ✅ 启用 | 读写本地文件系统（在沙箱中运行） |
| github | GitHub | ❌ 禁用 | GitHub 仓库管理（需要配置 token） |
| postgres | PostgreSQL | ❌ 禁用 | PostgreSQL 数据库操作（需要配置连接字符串） |
| slack | Slack | ❌ 禁用 | Slack 消息管理（需要配置 bot token） |
| brave-search | Brave 搜索 | ✅ 启用 | Brave 网页搜索引擎 |

## 实现细节

### 代码位置

- **初始化逻辑**: [backend/domains/agent/application/mcp_init.py](../../domains/agent/application/mcp_init.py)
- **启动集成**: [backend/bootstrap/main.py](../../bootstrap/main.py) (lifespan 函数)

### 工作流程

1. 应用启动时，在 `SessionManager` 启动后调用 `init_default_mcp_servers()`
2. 查询数据库中现有的系统级服务器
3. 对比默认配置，创建缺失的服务器
4. 如果服务器已存在，则跳过（幂等操作）
5. 记录初始化结果到日志

### 权限说明

- 所有默认服务器都是**系统级**（`scope='system'`, `user_id=NULL`）
- 对所有用户**可见**
- 只有**管理员**可以修改或删除
- 普通用户只能查看和启用/禁用（如果允许）

## 日志示例

```
INFO     - Default MCP servers initialization completed
INFO     - All default MCP servers already exist
```

或首次运行时：

```
INFO     - Creating default MCP server: filesystem
INFO     - Creating default MCP server: github
INFO     - Creating default MCP server: postgres
INFO     - Creating default MCP server: slack
INFO     - Creating default MCP server: brave-search
INFO     - Successfully created 5 default MCP server(s)
```

## 数据库迁移

默认服务器也会在数据库迁移时创建：
- **迁移文件**: [backend/alembic/versions/20260127_150000_add_mcp_servers.py](../../alembic/versions/20260127_150000_add_mcp_servers.py)
- **执行命令**: `alembic upgrade head`

## 测试

验证功能是否正常工作：

```bash
# 启动应用
cd backend
python -m bootstrap.main

# 查看日志，应该看到：
# INFO - Default MCP servers initialization completed
```

## 注意事项

- 初始化失败不会阻止应用启动（仅记录警告）
- 每次启动都会检查并创建缺失的服务器（幂等操作）
- 如果手动删除了默认服务器，重启后会自动重新创建
- 系统服务器的配置可以通过 API 修改（需要管理员权限）
