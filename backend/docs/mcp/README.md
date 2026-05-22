# MCP 工具管理系统 - 文档索引

本文档是 MCP (Model Context Protocol) 工具管理系统的文档导航。

## 📚 文档列表

| 文档 | 说明 | 适用对象 |
|------|------|---------|
| [MCP_QUICKSTART.md](./MCP_QUICKSTART.md) | 快速开始指南 | 新用户 |
| [MCP_STATUS_SYSTEM.md](./MCP_STATUS_SYSTEM.md) | 状态系统规范（前后端统一） | 开发者 |
| [MCP_AUTO_INIT.md](./MCP_AUTO_INIT.md) | 自动初始化说明 | 运维/开发者 |

---

## 🚀 快速开始

新用户请参阅 **[MCP_QUICKSTART.md](./MCP_QUICKSTART.md)**，了解：
- 启动步骤
- API 端点
- 测试方法

---

## 📊 状态系统

开发者请参阅 **[MCP_STATUS_SYSTEM.md](./MCP_STATUS_SYSTEM.md)**，了解：
- 状态定义和颜色规范
- 前后端类型定义
- React 组件示例

---

## 🔧 自动初始化

运维/开发者请参阅 **[MCP_AUTO_INIT.md](./MCP_AUTO_INIT.md)**，了解：
- 默认系统级服务器列表
- 启动时初始化流程
- 数据库迁移说明

---

## 📁 代码位置

```
backend/domains/agent/
├── domain/config/
│   ├── mcp_config.py                # 类型定义 (MCPScope, MCPServerEntityConfig)
│   └── templates/__init__.py        # 5 个内置模板
├── infrastructure/
│   ├── models/mcp_server.py         # ORM 模型
│   ├── repositories/mcp_server_repository.py
│   └── tools/mcp/
│       ├── wrapper.py
│       └── tool_service.py
├── application/
│   ├── mcp_use_case.py              # 业务逻辑
│   └── mcp_init.py                  # 自动初始化
└── presentation/
    ├── schemas/mcp_schemas.py
    └── mcp_router.py                # API 路由
```

---

## 🌐 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/mcp/templates` | 列出模板 |
| GET | `/api/v1/mcp/servers` | 列出服务器 |
| POST | `/api/v1/mcp/servers` | 添加服务器 |
| PUT | `/api/v1/mcp/servers/{id}` | 更新服务器 |
| DELETE | `/api/v1/mcp/servers/{id}` | 删除服务器 |
| PATCH | `/api/v1/mcp/servers/{id}/toggle` | 切换状态 |
| POST | `/api/v1/mcp/servers/{id}/test` | 测试连接 |
