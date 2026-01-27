# MCP 工具管理系统实施计划

**基于**: [2025-01-27-mcp-management-design.md](./2025-01-27-mcp-management-design.md)
**开始日期**: 2025-01-27
**预计工期**: 5-7 个工作日
**优先级**: 高

---

## 实施策略

采用 **增量实施** 策略，分阶段交付功能：

1. **Phase 1**：基础设施（Domain + Repository）
2. **Phase 2**：核心功能（UseCase + API）
3. **Phase 3**：前端界面
4. **Phase 4**：Session 集成
5. **Phase 5**：测试与优化

每阶段完成后可独立测试验证。

---

## Phase 1: 基础设施（1-2 天）

### 任务 1.1: Domain 层类型定义

**文件**：
- `backend/domains/agent/domain/config/mcp_config.py` (新建)

**内容**：
```python
from enum import Enum
from pydantic import BaseModel
from typing import Any, dict
import uuid

class MCPEnvironmentType(str, Enum):
    DYNAMIC_INJECTED = "dynamic_injected"
    PREINSTALLED = "preinstalled"
    CUSTOM_IMAGE = "custom_image"

class MCPScope(str, Enum):
    SYSTEM = "system"
    USER = "user"

class MCPServerConfig(BaseModel):
    id: uuid.UUID | None = None
    name: str
    display_name: str | None = None
    description: str | None = None
    url: str
    scope: MCPScope
    user_id: uuid.UUID | None = None
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

**验收标准**：
- 类型定义完整
- 通过类型检查（mypy）

---

### 任务 1.2: 数据库模型

**文件**：
- `backend/domains/agent/infrastructure/models/mcp_server.py` (新建)

**内容**：
```python
from sqlalchemy import Column, String, Text, Boolean, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from libs.db.base import Base

class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    url = Column(String(500), nullable=False)
    scope = Column(String(20), nullable=False)  # 'system' | 'user'
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    env_type = Column(String(50), nullable=False)
    env_config = Column(JSON, nullable=False, default=dict)
    api_key_env = Column(String(100))

    enabled = Column(Boolean, default=True)
    auto_start = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="mcp_servers")
```

**验收标准**：
- 模型定义完整
- 外键关系正确
- 通过迁移测试

---

### 任务 1.3: 数据库迁移

**文件**：
- `backend/alembic/versions/2025_01_27_add_mcp_servers.py` (新建)

**内容**：
- 创建 `mcp_servers` 表
- 扩展 `sessions` 表（添加 `mcp_config` 字段）
- 插入系统预置服务器（filesystem）

**执行步骤**：
```bash
cd backend
alembic revision -m "add mcp servers"
# 编辑生成的迁移文件
alembic upgrade head
```

**验收标准**：
- 迁移成功执行
- 表结构正确
- 索引创建成功
- system 服务器插入成功

---

### 任务 1.4: Repository 实现

**文件**：
- `backend/domains/agent/infrastructure/repositories/mcp_server_repository.py` (新建)

**核心方法**：
```python
class MCPServerRepository(OwnedRepositoryBase[MCPServer]):
    async def list_available(self) -> tuple[list[MCPServer], list[MCPServer]]:
        """返回 (system_servers, user_servers)"""

    def _apply_mcp_scope_filter(self, query: Select) -> Select:
        """MCP 特定过滤：system 服务器 + 用户自己的服务器"""

    async def get_by_name(self, name: str) -> MCPServer | None:
        """通过名称获取"""

    async def create(self, config: MCPServerConfig) -> MCPServer:
        """创建（强制 scope=user）"""

    async def update(self, server_id: UUID, updates: dict) -> MCPServer:
        """更新（检查权限）"""

    async def delete(self, server_id: UUID) -> None:
        """删除（检查权限）"""
```

**验收标准**：
- 继承 `OwnedRepositoryBase`
- 权限过滤逻辑正确
- system 服务器对所有用户可见
- user 服务器仅对所有者可见
- 通过单元测试

---

### 任务 1.5: 模板系统

**文件**：
- `backend/domains/agent/domain/config/mcp_templates.py` (新建)
- `backend/templates/mcp_builtin.py` (新建)

**内容**：
- 定义 `MCPTemplate` 类型
- 实现 `BUILTIN_TEMPLATES` 列表
- 实现 `TEMPLATE_CATEGORIES` 字典

**模板列表**：
1. github
2. filesystem
3. postgres
4. slack
5. brave-search

**验收标准**：
- 至少 5 个模板
- 模板字段完整
- 通过类型检查

---

## Phase 2: 核心功能（2 天）

### 任务 2.1: UseCase 实现

**文件**：
- `backend/domains/agent/application/mcp_use_case.py` (新建)

**核心方法**：
```python
class MCPManagementUseCase:
    async def list_servers(self) -> MCPServersListResponse
    async def list_templates(self) -> list[MCPTemplate]
    async def add_server(self, request, current_user) -> MCPServerConfig
    async def update_server(self, server_id, request, current_user) -> MCPServerConfig
    async def delete_server(self, server_id, current_user)
    async def test_connection(self, server_id, current_user) -> MCPTestResult
```

**业务规则**：
- 添加服务器强制 `scope=user`
- 修改服务器保护字段：`id, user_id, scope`
- 名称冲突检查
- 使用中服务器删除拦截

**验收标准**：
- 业务规则正确实现
- 权限检查完整
- 错误处理友好
- 通过单元测试

---

### 任务 2.2: API Schema

**文件**：
- `backend/domains/agent/presentation/schemas/mcp_schemas.py` (新建)

**Schema 定义**：
```python
class MCPServerCreateRequest(BaseModel):
    template_id: str | None = None
    name: str
    display_name: str | None = None
    url: str
    env_type: MCPEnvironmentType
    env_config: dict[str, Any] = {}
    api_key_env: str | None = None
    enabled: bool = True

class MCPServerUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    auto_start: bool | None = None

class MCPServersListResponse(BaseModel):
    system_servers: list[MCPServerConfig]
    user_servers: list[MCPServerConfig]

class MCPTestResult(BaseModel):
    connected: bool
    tools: list[dict] = []
    error: str | None = None
```

**验收标准**：
- Schema 定义完整
- 字段验证正确
- 通过类型检查

---

### 任务 2.3: API 路由

**文件**：
- `backend/domains/agent/presentation/mcp_router.py` (新建)
- `backend/domains/agent/presentation/deps.py` (扩展)

**路由清单**：
- `GET /api/mcp/templates` - 获取模板列表
- `GET /api/mcp/servers` - 获取服务器列表
- `POST /api/mcp/servers` - 添加服务器
- `PUT /api/mcp/servers/{id}` - 更新服务器
- `DELETE /api/mcp/servers/{id}` - 删除服务器
- `POST /api/mcp/servers/{id}/test` - 测试连接
- `PATCH /api/mcp/servers/{id}/toggle` - 启用/禁用
- `POST /api/mcp/admin/servers` - 创建系统服务器（仅管理员）

**依赖注入**：
```python
# presentation/deps.py
async def get_mcp_management_use_case(db: DbSession) -> MCPManagementUseCase:
    return MCPManagementUseCase(db)
```

**验收标准**：
- 所有路由正常工作
- 权限控制正确
- 错误处理完整
- 通过集成测试

---

### 任务 2.4: 注册路由

**文件**：
- `backend/bootstrap/main.py` (修改)

**步骤**：
1. 导入 `mcp_router`
2. 注册到 FastAPI app：`app.include_router(mcp_router, prefix="/api/mcp")`

**验收标准**：
- 路由正常注册
- API 文档包含新端点
- 访问 `/docs` 可见新路由

---

### 任务 2.5: MCP 客户端增强

**文件**：
- `backend/domains/agent/infrastructure/tools/mcp/client.py` (修改)

**增强内容**：
- 实现真实的 MCP 协议连接（替换 TODO）
- 添加重试逻辑（最多 2 次）
- 添加超时处理
- 改进错误消息

**验收标准**：
- 连接逻辑真实可用
- 重试机制正常工作
- 超时处理正确
- 错误消息友好

---

## Phase 3: 前端界面（1-2 天）

### 任务 3.1: API 客户端

**文件**：
- `frontend/src/api/mcp.ts` (新建)

**内容**：
```typescript
import { client } from './client'
import type {
  MCPServerConfig,
  MCPTemplate,
  MCPTestResult,
} from '@/types/mcp'

export const mcpApi = {
  listTemplates: () => client.get('/api/mcp/templates'),
  listServers: () => client.get('/api/mcp/servers'),
  addServer: (data: MCPServerCreateRequest) => client.post('/api/mcp/servers', data),
  updateServer: (id: string, data: MCPServerUpdateRequest) => client.put(`/api/mcp/servers/${id}`, data),
  deleteServer: (id: string) => client.delete(`/api/mcp/servers/${id}`),
  testConnection: (id: string) => client.post(`/api/mcp/servers/${id}/test`),
  toggleServer: (id: string, enabled: boolean) => client.patch(`/api/mcp/servers/${id}/toggle`, { enabled }),
}
```

**验收标准**：
- API 方法完整
- 类型定义正确
- 错误处理完善

---

### 任务 3.2: 类型定义

**文件**：
- `frontend/src/types/mcp.ts` (新建)

**内容**：
```typescript
export interface MCPServerConfig {
  id: string
  name: string
  display_name?: string
  description?: string
  url: string
  scope: 'system' | 'user'
  user_id?: string
  env_type: 'dynamic_injected' | 'preinstalled' | 'custom_image'
  env_config: Record<string, any>
  api_key_env?: string
  enabled: boolean
  auto_start: boolean
  created_at: string
  updated_at: string
}

export interface MCPTemplate {
  id: string
  name: string
  display_name: string
  description: string
  category: string
  icon?: string
  required_fields: string[]
  optional_fields: string[]
}

export interface MCPTestResult {
  connected: boolean
  tools: any[]
  error?: string
}
```

**验收标准**：
- 类型定义完整
- 与后端 Schema 一致

---

### 任务 3.3: 设置页面扩展

**文件**：
- `frontend/src/pages/settings/index.tsx` (修改)
- `frontend/src/pages/settings/components/mcp-servers-tab.tsx` (新建)

**组件列表**：
- `MCPServersTab` - 主容器
- `MCPServerList` - 服务器列表
- `MCPServerCard` - 服务器卡片
- `AddMCPServerDialog` - 添加对话框
- `TemplateSelector` - 模板选择器
- `TemplateConfigForm` - 模板配置表单
- `CustomServerForm` - 自定义表单

**步骤**：
1. 在 `index.tsx` 添加 "MCP 工具" 标签页
2. 实现 `MCPServersTab` 组件
3. 实现 `MCPServerList` 组件
4. 实现 `MCPServerCard` 组件（带健康状态、操作菜单）
5. 实现 `AddMCPServerDialog` 组件
6. 实现 `TemplateSelector` 组件（卡片式展示）
7. 实现 `TemplateConfigForm` 组件（动态表单）

**验收标准**：
- 所有组件正常工作
- UI 风格与现有设置页面一致
- 响应式布局（桌面 / 平板 / 移动）
- 加载状态、错误处理完善

---

### 任务 3.4: Session 配置面板

**文件**：
- `frontend/src/pages/chat/components/mcp-config-panel.tsx` (新建)

**功能**：
- 显示可用的服务器列表（system + user）
- 启用/禁用开关
- 显示已启用数量
- 调用 `sessionApi.updateMCPConfig()`

**集成**：
- 在对话页面侧边栏添加 "MCP 配置" 按钮
- 点击弹出对话框或展开面板

**验收标准**：
- 服务器列表正确显示
- 启用/禁用功能正常
- 状态同步正确

---

### 任务 3.5: Session API 扩展

**文件**：
- `frontend/src/api/session.ts` (修改)
- `frontend/src/api/client.ts` (修改)

**新增方法**：
```typescript
export const sessionApi = {
  // ... 现有方法 ...

  getMCPConfig: (sessionId: string) =>
    client.get(`/api/sessions/${sessionId}/mcp-config`),

  updateMCPConfig: (sessionId: string, config: SessionMCPConfig) =>
    client.put(`/api/sessions/${sessionId}/mcp-config`, config),
}
```

**验收标准**：
- API 方法正常工作
- 类型定义正确

---

## Phase 4: Session 集成（1 天）

### 任务 4.1: Session 模型扩展

**文件**：
- `backend/domains/agent/infrastructure/models/session.py` (修改)

**内容**：
- 添加 `mcp_config` 字段（JSON 类型）
- 默认值：`{}`

**验收标准**：
- 模型字段添加成功
- 迁移成功执行

---

### 任务 4.2: Session API 扩展

**文件**：
- `backend/domains/agent/presentation/session_router.py` (修改)
- `backend/domains/agent/application/session_use_case.py` (修改)

**新增端点**：
```python
@router.get("/{session_id}/mcp-config")
async def get_session_mcp_config(...)

@router.put("/{session_id}/mcp-config")
async def update_session_mcp_config(...)
```

**UseCase 方法**：
```python
async def update_mcp_config(
    self,
    session_id: UUID,
    config: SessionMCPConfig,
    current_user: CurrentUser,
) -> SessionMCPConfig:
    """验证：只能启用可用的服务器"""
    # 1. 获取可用服务器列表
    # 2. 验证启用的服务器在可用列表中
    # 3. 更新配置
```

**验收标准**：
- API 端点正常工作
- 验证逻辑正确
- 权限检查正确

---

### 任务 4.3: ChatUseCase 集成

**文件**：
- `backend/domains/agent/application/chat_use_case.py` (修改)

**集成步骤**：
1. 在 `process_message` 中加载 Session 的 `mcp_config`
2. 提取 `enabled_servers` 列表
3. 调用 `MCPManagementUseCase` 获取启用的服务器配置
4. 构建 `ExecutionConfig`（仅包含启用的 MCP 服务器）
5. 初始化 `ConfiguredMCPManager`
6. 调用 `list_all_tools()` 获取工具列表
7. 包装 MCP 工具（添加命名空间前缀）
8. 注册到 `ToolRegistry`
9. 执行 Agent 推理

**工具包装**：
```python
def _wrap_mcp_tool(self, tool_def: dict, mcp_manager: ConfiguredMCPManager) -> Tool:
    server_name = tool_def["mcp_server"]
    tool_name = tool_def["name"]

    async def executor(**kwargs):
        return await mcp_manager.call_tool(
            server_name=server_name,
            tool_name=tool_name,
            arguments=kwargs,
        )

    return Tool(
        name=f"{server_name}.{tool_name}",  # 命名空间隔离
        description=tool_def["description"],
        category=ToolCategory.MCP,
        func=executor,
    )
```

**验收标准**：
- Session MCP 配置正确加载
- 仅启用的服务器被初始化
- MCP 工具正确包装和注册
- Agent 可以调用 MCP 工具
- 通过 E2E 测试

---

## Phase 5: 测试与优化（1-2 天）

### 任务 5.1: 单元测试

**文件**：
- `backend/tests/unit/application/test_mcp_use_case.py` (新建)
- `backend/tests/unit/infrastructure/repositories/test_mcp_server_repository.py` (新建)

**测试用例**：
- Repository：权限过滤、CRUD 操作
- UseCase：业务规则验证、错误处理

**目标覆盖率**：80%+

**验收标准**：
- 所有核心路径有测试
- 测试通过
- 覆盖率达标

---

### 任务 5.2: 集成测试

**文件**：
- `backend/tests/integration/api/test_mcp_api.py` (新建)

**测试用例**：
- 权限测试（普通用户、管理员）
- CRUD 操作测试
- Session 集成测试

**验收标准**：
- 所有 API 端点有测试
- 权限控制正确
- 测试通过

---

### 任务 5.3: E2E 测试

**文件**：
- `backend/tests/e2e/test_mcp_workflow_e2e.py` (新建)

**测试场景**：
1. 管理员创建系统服务器
2. 普通用户查看系统服务器
3. 用户添加自定义服务器
4. 用户创建 Session 并配置 MCP
5. 用户发送消息，Agent 调用 MCP 工具
6. 清理资源

**验收标准**：
- 完整流程测试通过
- 所有功能验证成功

---

### 任务 5.4: 错误处理优化

**任务**：
- 统一异常类型
- 添加用户友好的错误消息
- 完善日志记录
- 添加监控指标（可选）

**验收标准**：
- 错误处理完善
- 错误消息友好
- 日志清晰有用

---

### 任务 5.5: 文档完善

**任务**：
- 更新 API 文档
- 编写用户使用指南
- 添加开发文档
- 更新 CHANGELOG

**验收标准**：
- 文档完整准确
- 用户可以自助使用
- 开发者可以维护

---

### 任务 5.6: 性能优化（可选）

**任务**：
- 添加缓存（模板列表）
- 优化数据库查询
- 批量操作支持
- 连接池优化

**验收标准**：
- 响应时间 < 500ms（P95）
- 数据库查询优化
- 无明显性能问题

---

## 部署清单

### 开发环境

- [ ] 完成 Phase 1-5
- [ ] 所有测试通过
- [ ] 代码审查通过

### 预发布环境

- [ ] 数据库迁移执行
- [ ] 配置文件更新
- [ ] 环境变量配置
- [ ] 冒烟测试通过

### 生产环境

- [ ] 数据库备份
- [ ] 迁移执行
- [ ] 服务部署
- [ ] 监控验证
- [ ] 回滚准备

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| MCP 协议变更 | 高 | 低 | 使用适配器模式，隔离协议变更 |
| 权限逻辑复杂 | 中 | 中 | 充分测试，代码审查 |
| 性能问题 | 中 | 低 | 缓存、连接池、监控 |
| 前端体验差 | 低 | 低 | 用户测试，迭代优化 |

---

## 依赖关系

```
Phase 1 (基础设施)
  ↓
Phase 2 (核心功能) ← Phase 1 完成
  ↓
Phase 3 (前端界面) ← Phase 2 完成
  ↓
Phase 4 (Session 集成) ← Phase 3 完成
  ↓
Phase 5 (测试与优化) ← Phase 4 完成
```

**关键路径**：Phase 1 → 2 → 4 → 5

**可并行**：Phase 3 可以与 Phase 4 并行开始部分工作

---

## 验收标准

### 功能验收

- [ ] 用户可以查看系统预置的 MCP 服务器
- [ ] 用户可以添加自定义 MCP 服务器
- [ ] 用户可以从模板快速创建服务器
- [ ] 用户可以在 Session 中启用/禁用 MCP 工具
- [ ] Agent 可以在对话中调用 MCP 工具
- [ ] 管理员可以管理系统服务器
- [ ] 权限控制正确

### 质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 所有集成测试通过
- [ ] E2E 测试通过
- [ ] 无严重 Bug
- [ ] 性能达标（P95 < 500ms）

### 文档验收

- [ ] API 文档完整
- [ ] 用户使用指南完成
- [ ] 开发文档完整
- [ ] CHANGELOG 更新

---

## 后续优化

详见设计方案第 12 节：

1. 批量操作
2. 导入/导出
3. 监控统计
4. 版本管理
5. 社区市场

---

## 附录

### A. 相关文档

- [设计方案](./2025-01-27-mcp-management-design.md)
- [权限系统架构](../PERMISSION_SYSTEM_ARCHITECTURE.md)
- [代码规范](../CODE_STANDARDS.md)

### B. 参考资料

- [MCP 协议规范](https://modelcontextprotocol.io/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [React Query 文档](https://tanstack.com/query/latest)

### C. 联系方式

- 技术问题：联系开发团队
- Bug 反馈：提交 Issue
- 功能建议：提交 Feature Request
