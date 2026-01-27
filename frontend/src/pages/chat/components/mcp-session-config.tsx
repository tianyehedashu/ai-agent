/**
 * Session MCP 配置面板
 * 用于在对话时配置启用的 MCP 工具
 */

import { useState } from 'react'
import type React from 'react'

import { useQuery, useMutation } from '@tanstack/react-query'
import { Settings as SettingsIcon, Check } from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import type { SessionMCPConfig } from '@/types/mcp'

interface MCPSessionConfigProps {
  sessionId: string
}

export function MCPSessionConfig({ sessionId }: MCPSessionConfigProps): React.ReactElement {
  const [open, setOpen] = useState(false)

  // 获取可用的服务器列表
  const { data: serversData, isLoading: serversLoading } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => mcpApi.listServers(),
    enabled: open, // 只在对话框打开时加载
  })

  // 获取当前 Session 的 MCP 配置
  const { data: currentConfig, isLoading: configLoading } = useQuery({
    queryKey: ['session-mcp-config', sessionId],
    queryFn: () => mcpApi.getSessionMCPConfig(sessionId),
    enabled: open,
  })

  // 更新 Session 配置
  const updateMutation = useMutation({
    mutationFn: (config: SessionMCPConfig) => mcpApi.updateSessionMCPConfig(sessionId, config),
    onSuccess: () => {
      toast.success('MCP 工具配置已更新')
      setOpen(false)
    },
    onError: (error: Error) => {
      toast.error(`更新失败: ${error.message}`)
    },
  })

  // 切换服务器启用状态
  const handleToggleServer = (serverId: string, enabled: boolean): void => {
    const enabledServers = currentConfig?.enabled_servers ?? []
    let newEnabledServers: string[]

    if (enabled) {
      // 添加服务器
      if (!enabledServers.includes(serverId)) {
        newEnabledServers = [...enabledServers, serverId]
      } else {
        return // 已经启用
      }
    } else {
      // 移除服务器
      newEnabledServers = enabledServers.filter((id) => id !== serverId)
    }

    updateMutation.mutate({ enabled_servers: newEnabledServers })
  }

  const allServers = [
    ...(serversData?.system_servers ?? []),
    ...(serversData?.user_servers ?? []),
  ].filter((server) => server.enabled) // 只显示已启用的服务器

  const enabledServerIds = new Set(currentConfig?.enabled_servers ?? [])

  if (serversLoading || configLoading) {
    return (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button variant="ghost" size="icon">
            <SettingsIcon className="h-4 w-4" />
          </Button>
        </DialogTrigger>
        <DialogContent>
          <div className="flex items-center justify-center py-8">加载中...</div>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" title="配置 MCP 工具">
          <SettingsIcon className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>配置 MCP 工具</DialogTitle>
          <DialogDescription>选择要在当前对话中使用的 MCP 工具</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {allServers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <p className="text-muted-foreground">暂无可用的 MCP 服务器</p>
              <p className="mt-2 text-sm text-muted-foreground">
                请在设置页面添加并启用 MCP 服务器
              </p>
            </div>
          ) : (
            <ScrollArea className="h-[400px] pr-4">
              <div className="space-y-3">
                {allServers.map((server) => {
                  const isEnabled = enabledServerIds.has(server.id)

                  return (
                    <div
                      key={server.id}
                      className="flex items-start justify-between rounded-lg border p-4 hover:bg-accent/50"
                    >
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{server.display_name ?? server.name}</span>
                          <Badge variant={server.scope === 'system' ? 'default' : 'secondary'}>
                            {server.scope === 'system' ? '系统' : '用户'}
                          </Badge>
                          {isEnabled && (
                            <Badge variant="outline" className="border-green-600 text-green-600">
                              <Check className="mr-1 h-3 w-3" />
                              已启用
                            </Badge>
                          )}
                        </div>
                        <p className="font-mono text-sm text-muted-foreground">{server.url}</p>
                        <p className="text-xs text-muted-foreground">类型: {server.env_type}</p>
                      </div>
                      <Switch
                        checked={isEnabled}
                        onCheckedChange={(checked) => {
                          handleToggleServer(server.id, checked)
                        }}
                        disabled={updateMutation.isPending}
                      />
                    </div>
                  )
                })}
              </div>
            </ScrollArea>
          )}
        </div>

        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            已启用 {enabledServerIds.size} / {allServers.length} 个工具
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setOpen(false)
            }}
            disabled={updateMutation.isPending}
          >
            完成
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
