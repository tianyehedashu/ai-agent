# 后端文档

FastAPI / `domains/` 分层架构的实现与设计文档。项目级文档见 [docs/README.md](../../docs/README.md)，AI Agent 规范见 [AGENTS.md](../../AGENTS.md)。

## 入门与规范

| 文档 | 说明 |
|------|------|
| [DEVELOPMENT.md](./DEVELOPMENT.md) | 后端开发快速入门 |
| [CODE_STANDARDS.md](./CODE_STANDARDS.md) | 代码规范与分层约定 |
| [PAGINATION.md](../../docs/PAGINATION.md) | 列表 API 分页 envelope（跨栈） |
| [API_RESPONSE.md](../../docs/API_RESPONSE.md) | API 响应 / RFC 7807 异常（跨栈） |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 后端架构概览（**实现权威**） |
| [CONFIGURATION.md](./CONFIGURATION.md) | 配置说明 |
| [LINT_CONFIGURATION.md](./LINT_CONFIGURATION.md) | Lint 配置 |

## Gateway

| 文档 | 说明 |
|------|------|
| [AI_GATEWAY_DOMAIN_ARCHITECTURE.md](./AI_GATEWAY_DOMAIN_ARCHITECTURE.md) | Gateway 域架构（**权威**） |
| [gateway/README.md](./gateway/README.md) | LiteLLM、接入、部署、定价等专题索引 |

## Agent 与上下文

| 文档 | 说明 |
|------|------|
| [AGENT_ARCHITECTURE_DESIGN.md](./AGENT_ARCHITECTURE_DESIGN.md) | Agent 架构设计（配置/实例/应用） |
| [LANGGRAPH_ARCHITECTURE_RATIONALE.md](./LANGGRAPH_ARCHITECTURE_RATIONALE.md) | LangGraph 选型理由 |
| [CONTEXT_MANAGEMENT_ARCHITECTURE.md](./CONTEXT_MANAGEMENT_ARCHITECTURE.md) | 上下文管理架构（**权威**） |
| [CONTEXT_MANAGEMENT_IMPLEMENTATION.md](./CONTEXT_MANAGEMENT_IMPLEMENTATION.md) | 上下文管理实现 |

论文对照、Token 优化与业界调研见 [archive/context/README.md](./archive/context/README.md)。

## MCP

| 文档 | 说明 |
|------|------|
| [mcp/README.md](./mcp/README.md) | MCP 总览与文档索引 |

历史 MCP 管理设计见 [archive/plans/README.md](./archive/plans/README.md)；全栈实施计划见 [docs/archive/plans/](../../docs/archive/plans/)；前端 UI 设计见 [frontend/docs/plans/2025-01-28-mcp-tool-management-design.md](../../frontend/docs/plans/2025-01-28-mcp-tool-management-design.md)。

## 权限、沙箱与垂直功能

| 文档 | 说明 |
|------|------|
| [PERMISSION_SYSTEM_ARCHITECTURE.md](./PERMISSION_SYSTEM_ARCHITECTURE.md) | 权限系统架构 |
| [项目权限规则.md](./项目权限规则.md) | 项目权限规则（产品向） |
| [execution-environment-config.md](./execution-environment-config.md) | 执行环境配置设计 |
| [沙箱资源管理设计文档.md](./沙箱资源管理设计文档.md) | 沙箱资源管理 |

视频生成完整实现见 [docs/VIDEO_GENERATION_IMPLEMENTATION.md](../../docs/VIDEO_GENERATION_IMPLEMENTATION.md)。

## 历史归档

| 文档 | 说明 |
|------|------|
| [archive/README.md](./archive/README.md) | 历史/过时文档总索引 |
