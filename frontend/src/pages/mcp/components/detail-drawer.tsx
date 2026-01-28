/**
 * MCP 服务器详情抽屉
 */

import { useState } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
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

export function DetailDrawer({
  server,
  open,
  onOpenChange,
}: DetailDrawerProps): React.ReactElement {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')

  // 暂时从 server.available_tools 提取工具列表
  // 后续会使用专门的 API
  const { data: toolsData, isLoading: toolsLoading } = useQuery({
    queryKey: ['mcp-server-tools', server?.id],
    queryFn: () => {
      if (!server) return []
      const availableTools = server.available_tools ?? {}
      const tools = Object.keys(availableTools).map((key) => ({
        name: key,
        description: typeof availableTools[key] === 'string' ? availableTools[key] : '',
        enabled: true,
        token_count: 0,
      }))
      return tools as ToolInfo[]
    },
    enabled: open && server !== null,
  })

  const tools = toolsData ?? []
  const filteredTools = tools.filter((tool) =>
    tool.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // 测试连接
  const testMutation = useMutation({
    mutationFn: (serverId: string) => mcpApi.testConnection(serverId),
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
          <div className="space-y-3 rounded-lg border p-4">
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
              <span className="text-sm">
                {enabledCount} / {toolCount}
              </span>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                testMutation.mutate(server.id)
              }}
              disabled={testMutation.isPending}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${testMutation.isPending ? 'animate-spin' : ''}`}
              />
              测试连接
            </Button>
          </div>

          {/* 工具列表 */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">工具列表</h3>
            </div>

            <Input
              placeholder="搜索工具..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
              }}
            />

            <div className="max-h-[400px] space-y-2 overflow-y-auto">
              {toolsLoading ? (
                <div className="py-8 text-center text-sm text-muted-foreground">加载中...</div>
              ) : filteredTools.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  {searchQuery ? '没有找到匹配的工具' : '暂无工具'}
                </div>
              ) : (
                filteredTools.map((tool) => (
                  <div
                    key={tool.name}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{tool.name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {tool.description ?? '无描述'}
                      </p>
                    </div>
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
