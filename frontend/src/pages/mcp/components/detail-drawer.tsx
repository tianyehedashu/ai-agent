/**
 * MCP 服务器详情抽屉
 */

import { useState } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Edit, RefreshCw, Trash2 } from 'lucide-react'
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
  onEdit?: (server: MCPServerConfig) => void
  onDelete?: (server: MCPServerConfig) => void
}

/**
 * Token 占用颜色规则:
 * - 绿色 (< 500 tokens): 低占用
 * - 黄色 (500-1500 tokens): 中等占用
 * - 红色 (> 1500 tokens): 高占用
 */
function getTokenColor(count: number): string {
  if (count < 500) return 'text-green-600 dark:text-green-400'
  if (count < 1500) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

function getTokenBadgeVariant(count: number): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (count < 500) return 'default'
  if (count < 1500) return 'secondary'
  return 'destructive'
}

export function DetailDrawer({
  server,
  open,
  onOpenChange,
  onEdit,
  onDelete,
}: DetailDrawerProps): React.ReactElement | null {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')

  // 使用新 API 获取工具列表
  const { data: toolsData, isLoading: toolsLoading } = useQuery({
    queryKey: ['mcp-server-tools', server?.id],
    queryFn: () =>
      server ? mcpApi.getServerTools(server.id) : Promise.reject(new Error('No server')),
    enabled: open && server !== null,
  })

  const tools = toolsData?.tools ?? []
  const enabledCount = toolsData?.enabled_count ?? 0
  const totalTokens = toolsData?.total_tokens ?? 0

  const filteredTools = tools.filter((tool) =>
    tool.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // 使用新 API 切换工具启用状态
  const toggleToolMutation = useMutation({
    mutationFn: ({ toolName, enabled }: { toolName: string; enabled: boolean }) =>
      server
        ? mcpApi.toggleToolEnabled(server.id, toolName, enabled)
        : Promise.reject(new Error('No server')),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-server-tools', server?.id] }).catch(() => {})
    },
    onError: (error: Error) => {
      toast.error(`操作失败: ${error.message}`)
    },
  })

  // 测试连接
  const testMutation = useMutation({
    mutationFn: () =>
      server ? mcpApi.testConnection(server.id) : Promise.reject(new Error('No server')),
    onSuccess: (result) => {
      toast.success(result.message)
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      queryClient.invalidateQueries({ queryKey: ['mcp-server-tools', server?.id] }).catch(() => {})
    },
    onError: (error: Error) => {
      toast.error(`测试失败: ${error.message}`)
    },
  })

  if (!server) return null

  const toolCount = tools.length

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
            {totalTokens > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">上下文占用</span>
                <Badge variant={getTokenBadgeVariant(totalTokens)} className="text-xs">
                  {totalTokens} tokens
                </Badge>
              </div>
            )}
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                testMutation.mutate()
              }}
              disabled={testMutation.isPending}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${testMutation.isPending ? 'animate-spin' : ''}`}
              />
              测试连接
            </Button>
            {onEdit && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onEdit(server)
                }}
              >
                <Edit className="mr-2 h-4 w-4" />
                编辑
              </Button>
            )}
            {onDelete && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onDelete(server)
                }}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                删除
              </Button>
            )}
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
                    className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{tool.name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {tool.description ?? '无描述'}
                      </p>
                      <p className={`text-xs ${getTokenColor(tool.token_count)}`}>
                        上下文: {tool.token_count} tokens
                      </p>
                    </div>
                    <Switch
                      checked={tool.enabled}
                      onCheckedChange={(checked) => {
                        toggleToolMutation.mutate({ toolName: tool.name, enabled: checked })
                      }}
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
