/**
 * MCP 服务器卡片（可展开）
 *
 * 折叠态：名称、URL、状态、启用开关。
 * 展开态：同卡片区域内展示测试/编辑/删除与工具列表，不弹出到别处。
 */

import { useState } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Edit, RefreshCw, Server, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { MCPServerConfig } from '@/types/mcp'

interface MCPServerCardProps {
  server: MCPServerConfig
  selected?: boolean
  className?: string
  onClick?: (server: MCPServerConfig) => void
  onToggle?: (server: MCPServerConfig, enabled: boolean) => void
  onEdit?: (server: MCPServerConfig) => void
  onDelete?: (server: MCPServerConfig) => void
}

const STATUS_COLOR_MAP: Record<string, string> = {
  gray: 'bg-muted-foreground/50',
  green: 'bg-emerald-500',
  red: 'bg-destructive',
  yellow: 'bg-amber-500',
}

function getTokenColor(count: number): string {
  if (count < 500) return 'text-emerald-600 dark:text-emerald-400'
  if (count < 1500) return 'text-amber-600 dark:text-amber-400'
  return 'text-destructive'
}

export function MCPServerCard({
  server,
  selected = false,
  className = '',
  onClick,
  onToggle,
  onEdit,
  onDelete,
}: MCPServerCardProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const [toolSearch, setToolSearch] = useState('')

  const displayName = server.display_name ?? server.name
  const statusColor = STATUS_COLOR_MAP[server.status_color ?? 'gray']
  const statusText = server.status_text ?? '未知'

  const { data: toolsData, isLoading: toolsLoading } = useQuery({
    queryKey: ['mcp-server-tools', server.id],
    queryFn: () => mcpApi.getServerTools(server.id),
    enabled: selected,
  })

  const tools = toolsData?.tools ?? []
  const enabledCount = toolsData?.enabled_count ?? 0
  const totalTokens = toolsData?.total_tokens ?? 0
  const filteredTools = tools.filter((t) =>
    t.name.toLowerCase().includes(toolSearch.toLowerCase())
  )

  const testMutation = useMutation({
    mutationFn: () => mcpApi.testConnection(server.id),
    onSuccess: (result) => {
      if (result.success) toast.success(result.message)
      else toast.error(result.message ?? result.error_details ?? '测试失败')
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] }).catch(() => {})
      queryClient.invalidateQueries({ queryKey: ['mcp-server-tools', server.id] }).catch(() => {})
    },
    onError: (e: Error) => toast.error(`测试失败: ${e.message}`),
  })

  const toggleToolMutation = useMutation({
    mutationFn: ({ toolName, enabled }: { toolName: string; enabled: boolean }) =>
      mcpApi.toggleToolEnabled(server.id, toolName, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-server-tools', server.id] }).catch(() => {})
    },
    onError: (e: Error) => toast.error(`操作失败: ${e.message}`),
  })

  const toolCount = tools.length

  return (
    <Card
      className={`overflow-hidden transition-all duration-200 ${selected ? 'ring-2 ring-primary/50 shadow-lg' : 'hover:shadow-md hover:border-muted-foreground/20'} ${className}`}
      onClick={() => onClick?.(server)}
    >
      {/* 头部：始终展示 */}
      <CardHeader className="pb-3 pt-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
            <Server className="h-5 w-5 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="truncate font-semibold text-foreground">{displayName}</h3>
              <Badge
                variant={server.scope === 'system' ? 'default' : 'secondary'}
                className="shrink-0 text-xs"
              >
                {server.scope === 'system' ? '内置' : '我的'}
              </Badge>
            </div>
            <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">{server.url}</p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5">
                <span
                  className={`inline-block h-2 w-2 shrink-0 rounded-full ${statusColor}`}
                  aria-hidden
                />
                <span className="text-xs text-muted-foreground">{statusText}</span>
              </div>
              <div
                className="flex items-center gap-2"
                onClick={(e) => e.stopPropagation()}
              >
                <span className="text-xs text-muted-foreground">启用</span>
                <Switch
                  checked={server.enabled}
                  onCheckedChange={(checked) => onToggle?.(server, checked)}
                />
              </div>
            </div>
          </div>
          <div className="shrink-0 text-muted-foreground">
            {selected ? (
              <ChevronDown className="h-5 w-5" />
            ) : (
              <ChevronRight className="h-5 w-5" />
            )}
          </div>
        </div>
      </CardHeader>

      {/* 展开区：测试、编辑、删除、工具列表 */}
      {selected && (
        <CardContent className="border-t bg-muted/30 pb-5 pt-4" onClick={(e) => e.stopPropagation()}>
          <div className="space-y-4">
            {/* 状态与操作 */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-background/80 px-4 py-3">
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <span className="text-muted-foreground">
                  工具 <strong className="text-foreground">{toolCount}</strong> 个
                </span>
                <span className="text-muted-foreground">
                  已启用 <strong className="text-foreground">{enabledCount}</strong> / {toolCount}
                </span>
                {totalTokens > 0 && (
                  <span className={`font-medium ${getTokenColor(totalTokens)}`}>
                    {totalTokens} tokens
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => testMutation.mutate()}
                          disabled={testMutation.isPending || !server.enabled}
                        >
                          <RefreshCw
                            className={`mr-1.5 h-4 w-4 ${testMutation.isPending ? 'animate-spin' : ''}`}
                          />
                          测试连接
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {!server.enabled ? '请先启用服务器' : '测试 MCP 连接并拉取工具'}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {onEdit && (
                  <Button variant="outline" size="sm" onClick={() => onEdit(server)}>
                    <Edit className="mr-1.5 h-4 w-4" />
                    编辑
                  </Button>
                )}
                {onDelete && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                    onClick={() => onDelete(server)}
                  >
                    <Trash2 className="mr-1.5 h-4 w-4" />
                    删除
                  </Button>
                )}
              </div>
            </div>
            {server.connection_status === 'failed' && server.last_error && (
              <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {server.last_error}
              </p>
            )}

            {/* 工具列表 */}
            <div className="rounded-lg border bg-background/80">
              <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
                <h4 className="text-sm font-medium">工具列表</h4>
                <Input
                  placeholder="搜索工具..."
                  value={toolSearch}
                  onChange={(e) => setToolSearch(e.target.value)}
                  className="h-8 max-w-[180px] text-xs"
                />
              </div>
              <div className="max-h-[280px] overflow-y-auto p-2">
                {toolsLoading ? (
                  <div className="py-8 text-center text-sm text-muted-foreground">加载中...</div>
                ) : filteredTools.length === 0 ? (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    {toolSearch ? '没有匹配的工具' : '暂无工具'}
                  </div>
                ) : (
                  <ul className="space-y-1.5">
                    {filteredTools.map((tool) => (
                      <li
                        key={tool.name}
                        className="flex items-center justify-between gap-2 rounded-md border border-transparent bg-muted/50 px-3 py-2 transition-colors hover:bg-muted/80"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{tool.name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {tool.description ?? '无描述'}
                          </p>
                          {tool.token_count > 0 && (
                            <p className={`text-xs ${getTokenColor(tool.token_count)}`}>
                              {tool.token_count} tokens
                            </p>
                          )}
                        </div>
                        <Switch
                          checked={tool.enabled}
                          onCheckedChange={(checked) =>
                            toggleToolMutation.mutate({ toolName: tool.name, enabled: checked })
                          }
                          disabled={toggleToolMutation.isPending}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}
