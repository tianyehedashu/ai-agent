# MCP 工具管理页面实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 构建独立的 MCP 工具管理页面，支持查看和管理 MCP 服务器及其工具、工具级别启用/禁用、Token 占用显示

**架构:** 前端独立页面 + 侧边抽屉详情，后端扩展 API 支持工具级别的操作和 Token 计算

**技术栈:** React, TypeScript, TanStack Query, Radix UI (Sheet), FastAPI, SQLAlchemy

---

## Phase 1: 前端基础结构

### Task 1: 添加 Sheet 组件

**Files:**
- Create: `frontend/src/components/ui/sheet.tsx`

**Step 1: Sheet 组件已创建**

文件已在 `frontend/src/components/ui/sheet.tsx` 创建完成，基于 `@radix-ui/react-dialog` 实现侧边抽屉功能。

**Step 2: 验证组件导出**

检查文件是否正确导出所有必需的子组件。

---

### Task 2: 创建 MCP 管理页面路由

**Files:**
- Modify: `frontend/src/App.tsx:30-35`
- Create: `frontend/src/pages/mcp/index.tsx`

**Step 1: 添加 MCP 页面路由到 App.tsx**

```typescript
// 在 App.tsx 中导入 MCPPage
import MCPPage from '@/pages/mcp'

// 在 Routes 中添加 MCP 路由（在 /settings 之前）
<Route path="/mcp" element={<MCPPage />} />
```

**Step 2: 创建 MCP 页面基础结构**

创建 `frontend/src/pages/mcp/index.tsx`:

```typescript
/**
 * MCP 工具管理页面
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search, Server } from 'lucide-react'

import { mcpApi } from '@/api/mcp'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MCPServerCard } from './components/server-card'
import { ImportDialog } from './components/import-dialog'

export default function MCPPage(): React.JSX.Element {
  const [searchQuery, setSearchQuery] = useState('')
  const [importDialogOpen, setImportDialogOpen] = useState(false)

  const { data: serversData, isLoading } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => mcpApi.listServers(),
  })

  const allServers = [...(serversData?.system_servers ?? []), ...(serversData?.user_servers ?? [])]

  const filteredServers = allServers.filter((server) => {
    const query = searchQuery.toLowerCase()
    const name = (server.display_name ?? server.name).toLowerCase()
    const url = server.url.toLowerCase()
    return name.includes(query) || url.includes(query)
  })

  return (
    <div className="container mx-auto p-6">
      {/* 页面头部 */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">MCP 工具中心</h1>
          <p className="mt-2 text-muted-foreground">
            管理和配置 Model Context Protocol 服务器与工具
          </p>
        </div>
        <Button onClick={() => setImportDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          添加服务器
        </Button>
      </div>

      {/* 搜索栏 */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索服务器..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* 服务器列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <span className="text-muted-foreground">加载中...</span>
        </div>
      ) : filteredServers.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
          <Server className="mb-4 h-12 w-12 text-muted-foreground" />
          <p className="text-muted-foreground">
            {searchQuery ? '没有找到匹配的服务器' : '暂无 MCP 服务器'}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            点击上方按钮添加您的第一个 MCP 服务器
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredServers.map((server) => (
            <MCPServerCard key={server.id} server={server} />
          ))}
        </div>
      )}

      {/* 导入对话框 */}
      <ImportDialog open={importDialogOpen} onOpenChange={setImportDialogOpen} />
    </div>
  )
}
```

**Step 3: 提交**

```bash
git add frontend/src/App.tsx frontend/src/pages/mcp/index.tsx
git commit -m "feat: add MCP management page with routing"
```

---

### Task 3: 创建服务器卡片组件

**Files:**
- Create: `frontend/src/pages/mcp/components/server-card.tsx`

**Step 1: 创建服务器卡片组件**

```typescript
/**
 * MCP 服务器卡片组件
 */

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import type { MCPServerConfig } from '@/types/mcp'

interface MCPServerCardProps {
  server: MCPServerConfig
}

export function MCPServerCard({ server }: MCPServerCardProps): React.ReactElement {
  const statusColor = {
    gray: 'bg-gray-500',
    green: 'bg-green-500',
    red: 'bg-red-500',
    yellow: 'bg-yellow-500',
  }[server.status_color ?? 'gray']

  return (
    <Card className="hover:shadow-md transition-shadow cursor-pointer">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg">
                {server.display_name ?? server.name}
              </CardTitle>
              <Badge variant={server.scope === 'system' ? 'default' : 'secondary'}>
                {server.scope === 'system' ? '系统' : '用户'}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground font-mono truncate">
              {server.url}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className={`h-2 w-2 rounded-full ${statusColor}`} />
            <Switch checked={server.enabled} />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">状态:</span>
            <span>{server.status_text ?? '未知'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">工具数:</span>
            <span>
              {Object.keys(server.available_tools ?? {}).length} 个工具
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

**Step 2: 提交**

```bash
git add frontend/src/pages/mcp/components/server-card.tsx
git commit -m "feat: add MCP server card component"
```

---

### Task 4: 创建导入对话框组件

**Files:**
- Create: `frontend/src/pages/mcp/components/import-dialog.tsx`

**Step 1: 创建导入对话框**

```typescript
/**
 * 导入 MCP 服务器对话框
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import type { MCPTemplate } from '@/types/mcp'

interface ImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ImportDialog({ open, onOpenChange }: ImportDialogProps): React.ReactElement {
  const queryClient = useQueryClient()
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')

  // 获取模板列表
  const { data: templates } = useQuery({
    queryKey: ['mcp-templates'],
    queryFn: () => mcpApi.listTemplates(),
    enabled: open,
  })

  const selectedTemplate = templates?.find((t) => t.id === selectedTemplateId)

  // 添加服务器
  const addMutation = useMutation({
    mutationFn: (data: { name: string; url: string; template_id?: string }) =>
      mcpApi.addServer({
        ...data,
        env_type: 'dynamic_injected',
        env_config: {},
        enabled: true,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      onOpenChange(false)
      setName('')
      setUrl('')
      setSelectedTemplateId('')
      toast.success('服务器添加成功')
    },
    onError: (error: Error) => {
      toast.error(`添加失败: ${error.message}`)
    },
  })

  const handleTemplateChange = (templateId: string): void => {
    setSelectedTemplateId(templateId)
    const template = templates?.find((t) => t.id === templateId)
    if (template) {
      setName(template.name)
      setUrl(template.default_config.url)
    }
  }

  const handleAdd = (): void => {
    if (!name || !url) {
      toast.error('请填写完整信息')
      return
    }
    addMutation.mutate({ name, url, template_id: selectedTemplateId || undefined })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>添加 MCP 服务器</DialogTitle>
          <DialogDescription>从模板添加或手动配置 MCP 服务器</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="template">选择模板（可选）</Label>
            <Select value={selectedTemplateId} onValueChange={handleTemplateChange}>
              <SelectTrigger id="template">
                <SelectValue placeholder="选择模板或手动输入" />
              </SelectTrigger>
              <SelectContent>
                {templates?.map((template) => (
                  <SelectItem key={template.id} value={template.id}>
                    <div className="flex items-center gap-2">
                      <span>{template.display_name}</span>
                      <Badge variant="outline" className="text-xs">
                        {template.category}
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedTemplate && (
              <p className="text-sm text-muted-foreground">{selectedTemplate.description}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="name">服务器名称</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-mcp-server"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="url">服务器 URL</Label>
            <Input
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="stdio://mcp-server 或 https://..."
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button onClick={handleAdd} disabled={addMutation.isPending}>
            {addMutation.isPending ? '添加中...' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

**Step 2: 添加缺失的导入**

在文件顶部添加 `useQuery`:

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
```

**Step 3: 提交**

```bash
git add frontend/src/pages/mcp/components/import-dialog.tsx
git commit -m "feat: add MCP import dialog component"
```

---

## Phase 2: 侧边抽屉详情页

### Task 5: 创建详情抽屉组件

**Files:**
- Create: `frontend/src/pages/mcp/components/detail-drawer.tsx`
- Modify: `frontend/src/pages/mcp/components/server-card.tsx`

**Step 1: 创建详情抽屉组件**

创建 `frontend/src/pages/mcp/components/detail-drawer.tsx`:

```typescript
/**
 * MCP 服务器详情抽屉
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Plus, Settings } from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Switch } from '@/components/ui/switch'
import type { MCPServerConfig } from '@/types/mcp'

interface DetailDrawerProps {
  server: MCPServerConfig | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface ToolInfo {
  name: string
  description?: string
  enabled: boolean
  token_count?: number
}

export function DetailDrawer({ server, open, onOpenChange }: DetailDrawerProps): React.ReactElement {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')

  // 获取服务器工具列表（需要后端 API 支持）
  const { data: toolsData, isLoading: toolsLoading } = useQuery({
    queryKey: ['mcp-server-tools', server?.id],
    queryFn: async () => {
      if (!server) return []
      // 暂时使用 available_tools，后续添加专门的 API
      const tools = Object.keys(server.available_tools ?? {}).map((key) => ({
        name: key,
        description: String((server.available_tools ?? {})[key] ?? ''),
        enabled: true,
        token_count: 0, // 需要后端计算
      }))
      return tools as ToolInfo[]
    },
    enabled: open && !!server,
  })

  const tools = toolsData ?? []

  const filteredTools = tools.filter((tool) =>
    tool.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // 切换工具启用状态
  const toggleToolMutation = useMutation({
    mutationFn: ({ toolName, enabled }: { toolName: string; enabled: boolean }) => {
      // 需要 API: PATCH /api/v1/mcp/servers/{id}/tools/{toolName}/enabled
      return mcpApi.updateServer(server!.id, {
        available_tools: {
          ...(server!.available_tools ?? {}),
          [toolName]: { enabled },
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-server-tools', server?.id] }).catch(() => {})
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
    },
    onError: (error: Error) => {
      toast.error(`操作失败: ${error.message}`)
    },
  })

  // 测试连接
  const testMutation = useMutation({
    mutationFn: () => mcpApi.testConnection(server!.id),
    onSuccess: (result) => {
      toast.success(result.message)
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
    },
    onError: (error: Error) => {
      toast.error(`测试失败: ${error.message}`)
    },
  })

  if (!server) return null

  const toolCount = Object.keys(server.available_tools ?? {}).length
  const enabledCount = filteredTools.filter((t) => t.enabled).length

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{server.display_name ?? server.name}</SheetTitle>
          <SheetDescription>{server.url}</SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* 服务器信息 */}
          <div className="rounded-lg border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">状态</span>
              <Badge variant={server.enabled ? 'default' : 'secondary'}>
                {server.status_text ?? '未知'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">工具数量</span>
              <span className="text-sm">{toolCount} 个</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">已启用</span>
              <span className="text-sm">{enabledCount} / {toolCount}</span>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${testMutation.isPending ? 'animate-spin' : ''}`} />
              测试连接
            </Button>
            <Button variant="outline" size="sm">
              <Settings className="mr-2 h-4 w-4" />
              配置
            </Button>
          </div>

          {/* 工具列表 */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">工具列表</h3>
              <Button size="sm" variant="outline">
                <Plus className="mr-2 h-4 w-4" />
                添加工具
              </Button>
            </div>

            <Input
              placeholder="搜索工具..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {toolsLoading ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  加载中...
                </div>
              ) : filteredTools.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  {searchQuery ? '没有找到匹配的工具' : '暂无工具'}
                </div>
              ) : (
                filteredTools.map((tool) => (
                  <div
                    key={tool.name}
                    className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{tool.name}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {tool.description || '无描述'}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-muted-foreground">
                          上下文: {tool.token_count ?? '?'} tokens
                        </span>
                      </div>
                    </div>
                    <Switch
                      checked={tool.enabled}
                      onCheckedChange={(checked) =>
                        toggleToolMutation.mutate({ toolName: tool.name, enabled: checked })
                      }
                      disabled={toggleToolMutation.isPending}
                    />
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

**Step 2: 修改 server-card 添加点击事件**

修改 `frontend/src/pages/mcp/components/server-card.tsx`:

```typescript
import { useBoolean } from '@/hooks/use-boolean' // 或者直接使用 useState

interface MCPServerCardProps {
  server: MCPServerConfig
  onClick?: (server: MCPServerConfig) => void
}

export function MCPServerCard({ server, onClick }: MCPServerCardProps): React.ReactElement {
  return (
    <Card
      className="hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => onClick?.(server)}
    >
      {/* ... 其他内容保持不变 */}
    </Card>
  )
}
```

**Step 3: 更新 MCP 页面集成抽屉**

修改 `frontend/src/pages/mcp/index.tsx`:

```typescript
import { DetailDrawer } from './components/detail-drawer'

export default function MCPPage(): React.JSX.Element {
  const [selectedServer, setSelectedServer] = useState<MCPServerConfig | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ...

  return (
    <div className="container mx-auto p-6">
      {/* ... 其他内容 */}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredServers.map((server) => (
          <MCPServerCard
            key={server.id}
            server={server}
            onClick={(s) => {
              setSelectedServer(s)
              setDrawerOpen(true)
            }}
          />
        ))}
      </div>

      <DetailDrawer
        server={selectedServer}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </div>
  )
}
```

**Step 4: 提交**

```bash
git add frontend/src/pages/mcp/components/detail-drawer.tsx frontend/src/pages/mcp/components/server-card.tsx frontend/src/pages/mcp/index.tsx
git commit -m "feat: add MCP server detail drawer with tool list"
```

---

## Phase 3: 后端 API 扩展

### Task 6: 扩展 MCP Schema 支持工具信息

**Files:**
- Modify: `backend/domains/agent/presentation/schemas/mcp_schemas.py`

**Step 1: 添加工具相关 Schema**

在 `mcp_schemas.py` 中添加:

```python
class MCPToolInfo(BaseModel):
    """MCP 工具信息"""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    token_count: int = 0


class MCPToolsListResponse(BaseModel):
    """MCP 工具列表响应"""

    server_id: uuid.UUID
    server_name: str
    tools: list[MCPToolInfo]
    total_tokens: int = 0
    enabled_count: int = 0


class MCPToolToggleRequest(BaseModel):
    """工具启用/禁用请求"""

    enabled: bool = Field(..., description="是否启用该工具")
```

**Step 2: 提交**

```bash
git add backend/domains/agent/presentation/schemas/mcp_schemas.py
git commit -m "feat: add MCP tool info schemas"
```

---

### Task 7: 添加工具列表 API 端点

**Files:**
- Modify: `backend/domains/agent/presentation/mcp_router.py`

**Step 1: 添加工具列表端点**

在 `mcp_router.py` 中添加:

```python
from domains.agent.presentation.schemas.mcp_schemas import (
    # ... 现有导入
    MCPToolInfo,
    MCPToolsListResponse,
    MCPToolToggleRequest,
)


@router.get(
    "/servers/{server_id}/tools",
    summary="获取 MCP 服务器的工具列表",
)
async def list_server_tools(
    server_id: uuid.UUID,
    current_user: AuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPToolsListResponse:
    """获取 MCP 服务器的工具列表及 Token 占用"""
    return await use_case.list_server_tools(server_id, current_user)


@router.put(
    "/servers/{server_id}/tools/{tool_name}/enabled",
    summary="切换工具启用状态",
)
async def toggle_tool_enabled(
    server_id: uuid.UUID,
    tool_name: str,
    request: MCPToolToggleRequest,
    current_user: RequiredAuthUser,
    use_case: MCPManagementUseCase = Depends(get_mcp_service),
) -> MCPToolInfo:
    """启用或禁用特定工具"""
    return await use_case.toggle_tool_enabled(server_id, tool_name, request.enabled, current_user)
```

**Step 2: 提交**

```bash
git add backend/domains/agent/presentation/mcp_router.py
git commit -m "feat: add MCP tools list and toggle endpoints"
```

---

### Task 8: 实现 UseCase 方法

**Files:**
- Modify: `backend/domains/agent/application/mcp_use_case.py`

**Step 1: 添加工具列表方法**

在 `MCPManagementUseCase` 类中添加:

```python
from domains.agent.presentation.schemas.mcp_schemas import MCPToolsListResponse, MCPToolInfo

async def list_server_tools(
    self, server_id: uuid.UUID, current_user: Principal
) -> MCPToolsListResponse:
    """获取服务器的工具列表"""
    server = await self._get_accessible_server(server_id, current_user)

    # 从 available_tools 中提取工具信息
    tools_data = server.available_tools or {}
    tools = []

    for tool_name, tool_config in tools_data.items():
        if isinstance(tool_config, dict):
            tool_info = MCPToolInfo(
                name=tool_name,
                description=tool_config.get("description"),
                input_schema=tool_config.get("inputSchema", {}),
                enabled=tool_config.get("enabled", True),
                token_count=self._calculate_token_count(tool_config),
            )
            tools.append(tool_info)

    total_tokens = sum(t.token_count for t in tools)
    enabled_count = sum(1 for t in tools if t.enabled)

    return MCPToolsListResponse(
        server_id=server.id,
        server_name=server.name,
        tools=tools,
        total_tokens=total_tokens,
        enabled_count=enabled_count,
    )

async def toggle_tool_enabled(
    self, server_id: uuid.UUID, tool_name: str, enabled: bool, current_user: Principal
) -> MCPToolInfo:
    """切换工具启用状态"""
    server = await self._get_accessible_server(server_id, current_user)

    tools = dict(server.available_tools or {})
    if tool_name not in tools:
        raise ValueError(f"Tool {tool_name} not found")

    if isinstance(tools[tool_name], dict):
        tools[tool_name]["enabled"] = enabled
    else:
        tools[tool_name] = {"enabled": enabled, "config": tools[tool_name]}

    server.available_tools = tools
    await self.repository.update(server)

    tool_config = tools[tool_name]
    return MCPToolInfo(
        name=tool_name,
        description=tool_config.get("description") if isinstance(tool_config, dict) else None,
        input_schema=tool_config.get("inputSchema", {}) if isinstance(tool_config, dict) else {},
        enabled=enabled,
        token_count=self._calculate_token_count(tool_config),
    )

def _calculate_token_count(self, tool_config: Any) -> int:
    """计算工具定义的 Token 占用"""
    import json
    import tiktoken

    try:
        # 使用 GPT-4 的 tokenizer
        encoding = tiktoken.encoding_for_model("gpt-4")

        # 构建工具定义字符串
        tool_def = {
            "name": tool_config.get("name", ""),
            "description": tool_config.get("description", ""),
            "inputSchema": tool_config.get("inputSchema", {}),
        }
        tool_str = json.dumps(tool_def, ensure_ascii=False)

        # 计算 token 数量
        return len(encoding.encode(tool_str))
    except Exception:
        # 如果计算失败，使用估算: 1 token ≈ 4 字符
        tool_str = json.dumps(tool_config, ensure_ascii=False)
        return len(tool_str) // 4
```

**Step 2: 提交**

```bash
git add backend/domains/agent/application/mcp_use_case.py
git commit -m "feat: implement list_server_tools and toggle_tool_enabled in UseCase"
```

---

## Phase 4: 前端 API 更新

### Task 9: 更新前端 API 客户端

**Files:**
- Modify: `frontend/src/api/mcp.ts`
- Modify: `frontend/src/types/mcp.ts`

**Step 1: 添加类型定义**

在 `frontend/src/types/mcp.ts` 中添加:

```typescript
/** MCP 工具信息 */
export interface MCPToolInfo {
  name: string
  description?: string
  inputSchema?: Record<string, unknown>
  enabled: boolean
  token_count: number
}

/** MCP 工具列表响应 */
export interface MCPToolsListResponse {
  server_id: string
  server_name: string
  tools: MCPToolInfo[]
  total_tokens: number
  enabled_count: number
}
```

**Step 2: 添加 API 方法**

在 `frontend/src/api/mcp.ts` 中添加:

```typescript
import type {
  // ... 现有导入
  MCPToolInfo,
  MCPToolsListResponse,
} from '@/types/mcp'

export const mcpApi = {
  // ... 现有方法

  /**
   * 获取服务器的工具列表
   */
  async getServerTools(id: string): Promise<MCPToolsListResponse> {
    return apiClient.get<MCPToolsListResponse>(`/api/v1/mcp/servers/${id}/tools`)
  },

  /**
   * 切换工具启用状态
   */
  async toggleToolEnabled(serverId: string, toolName: string, enabled: boolean): Promise<MCPToolInfo> {
    return apiClient.put<MCPToolInfo>(
      `/api/v1/mcp/servers/${serverId}/tools/${encodeURIComponent(toolName)}/enabled`,
      { enabled }
    )
  },
}
```

**Step 3: 提交**

```bash
git add frontend/src/api/mcp.ts frontend/src/types/mcp.ts
git commit -m "feat: add MCP tools API client methods and types"
```

---

### Task 10: 更新详情抽屉使用新 API

**Files:**
- Modify: `frontend/src/pages/mcp/components/detail-drawer.tsx`

**Step 1: 修改工具列表查询**

```typescript
// 修改 useQuery
const { data: toolsData, isLoading: toolsLoading } = useQuery({
  queryKey: ['mcp-server-tools', server?.id],
  queryFn: () => mcpApi.getServerTools(server!.id),
  enabled: open && !!server,
})

const toolsList = toolsData?.tools ?? []
const enabledCount = toolsData?.enabled_count ?? 0
const totalTokens = toolsData?.total_tokens ?? 0
```

**Step 2: 修改切换工具逻辑**

```typescript
const toggleToolMutation = useMutation({
  mutationFn: ({ toolName, enabled }: { toolName: string; enabled: boolean }) =>
    mcpApi.toggleToolEnabled(server!.id, toolName, enabled),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['mcp-server-tools', server?.id] }).catch(() => {})
  },
  // ...
})
```

**Step 3: 提交**

```bash
git add frontend/src/pages/mcp/components/detail-drawer.tsx
git commit -m "feat: update detail drawer to use new tools API"
```

---

## Phase 5: UI 优化

### Task 11: 添加 Token 占用颜色标识

**Files:**
- Modify: `frontend/src/pages/mcp/components/detail-drawer.tsx`

**Step 1: 添加辅助函数**

```typescript
function getTokenColor(count: number): string {
  if (count < 500) return 'text-green-600'
  if (count < 1500) return 'text-yellow-600'
  return 'text-red-600'
}

function getTokenBadgeColor(count: number): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (count < 500) return 'default'
  if (count < 1500) return 'secondary'
  return 'destructive'
}
```

**Step 2: 更新 Token 显示**

```typescript
<span className={`text-xs ${getTokenColor(tool.token_count ?? 0)}`}>
  上下文: {tool.token_count ?? '?'} tokens
</span>
```

**Step 3: 提交**

```bash
git add frontend/src/pages/mcp/components/detail-drawer.tsx
git commit -m "feat: add token count color indicators"
```

---

### Task 12: 添加导航菜单入口

**Files:**
- Modify: `frontend/src/components/layout/header.tsx` (或其他导航文件)

**Step 1: 添加 MCP 入口**

在导航菜单中添加:

```typescript
import { Link } from 'react-router-dom'

// 在导航项中添加
<Link to="/mcp" className="nav-item">
  <Server className="h-4 w-4" />
  <span>MCP 工具</span>
</Link>
```

**Step 2: 提交**

```bash
git add frontend/src/components/layout/header.tsx
git commit -m "feat: add MCP tools navigation link"
```

---

## Phase 6: 测试

### Task 13: 端到端测试

**Files:**
- Create: `frontend/tests/mcp/mcp-page.test.tsx`
- Create: `backend/tests/integration/api/test_mcp_tools_api.py`

**Step 1: 创建前端测试**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import MCPPage from '@/pages/mcp'

// Mock API
vi.mock('@/api/mcp', () => ({
  mcpApi: {
    listServers: vi.fn(() => Promise.resolve({
      system_servers: [],
      user_servers: [],
    })),
    listTemplates: vi.fn(() => Promise.resolve([])),
  },
}))

describe('MCPPage', () => {
  it('renders page title', async () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MCPPage />
      </QueryClientProvider>
    )

    expect(screen.getByText('MCP 工具中心')).toBeInTheDocument()
  })

  it('shows empty state when no servers', async () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MCPPage />
      </QueryClientProvider>
    )

    await waitFor(() => {
      expect(screen.getByText(/暂无 MCP 服务器/)).toBeInTheDocument()
    })
  })
})
```

**Step 2: 创建后端测试**

```python
import pytest
from httpx import AsyncClient

from tests.conftest import client


@pytest.mark.asyncio
async def test_list_server_tools(authenticated_client: AsyncClient, mcp_server):
    """测试获取服务器工具列表"""
    response = await authenticated_client.get(f"/api/v1/mcp/servers/{mcp_server.id}/tools")

    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert "server_id" in data


@pytest.mark.asyncio
async def test_toggle_tool_enabled(authenticated_client: AsyncClient, mcp_server):
    """测试切换工具启用状态"""
    response = await authenticated_client.put(
        f"/api/v1/mcp/servers/{mcp_server.id}/tools/test_tool/enabled",
        json={"enabled": False}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
```

**Step 3: 运行测试**

```bash
# 前端测试
cd frontend && npm run test

# 后端测试
cd backend && pytest tests/integration/api/test_mcp_tools_api.py -v
```

**Step 4: 提交**

```bash
git add frontend/tests/mcp/ backend/tests/integration/api/test_mcp_tools_api.py
git commit -m "test: add MCP tools management tests"
```

---

## 完成清单

- [ ] Sheet 组件已创建
- [ ] MCP 页面路由已添加
- [ ] 服务器卡片组件已创建
- [ ] 导入对话框已创建
- [ ] 详情抽屉已创建
- [ ] 后端 Schema 已扩展
- [ ] 后端 API 端点已添加
- [ ] UseCase 方法已实现
- [ ] 前端 API 客户端已更新
- [ ] Token 占用计算已实现
- [ ] 颜色标识已添加
- [ ] 导航菜单入口已添加
- [ ] 测试已创建并通过

---

**估计总时间:** 4-6 小时
**优先级:** P0 (核心功能) + P1 (工具管理) + P2 (UI 优化)
