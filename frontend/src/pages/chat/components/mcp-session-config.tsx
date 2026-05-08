/**
 * Session 对话工具与 MCP 配置
 *
 * 使用抽屉（Sheet）展示两类配置：
 * 1. 对话工具说明（内置工具由 Agent 决定）
 * 2. MCP 服务器（选择在本对话中启用的 MCP 服务器）
 */

import { useState } from 'react'
import type React from 'react'

import { useQuery, useMutation } from '@tanstack/react-query'
import { Check, Plug, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Switch } from '@/components/ui/switch'
import { useChatStore } from '@/stores/chat'
import type { SessionMCPConfig } from '@/types/mcp'

interface MCPSessionConfigProps {
  /** 无 session 时使用本地待用配置（pendingMCPConfig） */
  sessionId: string | undefined
  /** 受控模式：由父组件控制开关，不渲染默认触发按钮 */
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function MCPSessionConfig({
  sessionId,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: MCPSessionConfigProps): React.ReactElement {
  const [internalOpen, setInternalOpen] = useState(false)
  const isControlled = controlledOpen !== undefined && controlledOnOpenChange !== undefined
  const open = isControlled ? controlledOpen : internalOpen
  const setOpen = isControlled ? controlledOnOpenChange : setInternalOpen

  const { pendingMCPConfig, setPendingMCPConfig } = useChatStore()

  const { data: serversData, isLoading: serversLoading } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => mcpApi.listServers(),
    enabled: open,
  })

  const { data: currentConfig, isLoading: configLoading } = useQuery({
    queryKey: ['session-mcp-config', sessionId],
    queryFn: () => {
      if (!sessionId) throw new Error('sessionId required')
      return mcpApi.getSessionMCPConfig(sessionId)
    },
    enabled: open && !!sessionId,
  })

  const updateMutation = useMutation({
    mutationFn: (config: SessionMCPConfig) => {
      if (!sessionId) throw new Error('sessionId required')
      return mcpApi.updateSessionMCPConfig(sessionId, config)
    },
    onSuccess: () => {
      toast.success('对话工具配置已更新')
      setOpen(false)
    },
    onError: (error: Error) => {
      toast.error(`更新失败: ${error.message}`)
    },
  })

  const handleToggleServer = (serverId: string, enabled: boolean): void => {
    if (sessionId) {
      const enabledServers = currentConfig?.enabled_servers ?? []
      const newEnabledServers = enabled
        ? enabledServers.includes(serverId)
          ? enabledServers
          : [...enabledServers, serverId]
        : enabledServers.filter((id) => id !== serverId)
      updateMutation.mutate({ enabled_servers: newEnabledServers })
    } else {
      const newEnabledServers = enabled
        ? pendingMCPConfig.includes(serverId)
          ? pendingMCPConfig
          : [...pendingMCPConfig, serverId]
        : pendingMCPConfig.filter((id) => id !== serverId)
      setPendingMCPConfig(newEnabledServers)
    }
  }

  const allServers = [
    ...(serversData?.system_servers ?? []),
    ...(serversData?.user_servers ?? []),
  ].filter((server) => server.enabled)

  const enabledServerIds = new Set(
    sessionId ? (currentConfig?.enabled_servers ?? []) : pendingMCPConfig
  )
  const loading = sessionId ? serversLoading || configLoading : serversLoading

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      {!isControlled && (
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 rounded-full bg-background/80 px-3 text-xs text-muted-foreground shadow-sm backdrop-blur-sm hover:bg-background hover:text-foreground"
            title="配置本对话可用的工具与 MCP 服务器"
          >
            <Wrench className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">对话工具</span>
          </Button>
        </SheetTrigger>
      )}
      <SheetContent side="right" className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Wrench className="h-5 w-5" />
            对话工具与 MCP
          </SheetTitle>
          <SheetDescription>
            选择在本对话中可用的工具来源：内置工具由 Agent 配置决定，下方可启用 MCP
            服务器以扩展工具。
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 flex flex-1 flex-col gap-6 overflow-hidden">
          {/* 第一类：对话工具说明 */}
          <section className="space-y-2 rounded-lg border bg-muted/30 p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Wrench className="h-4 w-4 text-muted-foreground" />
              内置工具
            </h3>
            <p className="text-xs text-muted-foreground">
              本对话可用的内置工具（如读写文件、执行命令等）由当前 Agent 配置决定，无需在此选择。
            </p>
          </section>

          {/* 第二类：MCP 服务器 */}
          <section className="flex flex-1 flex-col gap-3 overflow-hidden">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Plug className="h-4 w-4 text-muted-foreground" />
              MCP 服务器
            </h3>
            <p className="text-xs text-muted-foreground">
              启用后，该服务器提供的工具将可供 AI 在本对话中调用。
            </p>

            {loading ? (
              <div className="flex flex-1 items-center justify-center py-8 text-sm text-muted-foreground">
                加载中...
              </div>
            ) : allServers.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed py-8 text-center">
                <Plug className="mb-3 h-10 w-10 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">暂无可用的 MCP 服务器</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  请在「MCP 服务器」页面添加并启用
                </p>
              </div>
            ) : (
              <ScrollArea className="flex-1 pr-2">
                <div className="space-y-2 pb-4">
                  {allServers.map((server) => {
                    const isEnabled = enabledServerIds.has(server.id)
                    return (
                      <div
                        key={server.id}
                        className="flex items-start justify-between gap-3 rounded-lg border p-3 transition-colors hover:bg-accent/50"
                      >
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">
                              {server.display_name ?? server.name}
                            </span>
                            <Badge
                              variant={server.scope === 'system' ? 'default' : 'secondary'}
                              className="text-xs"
                            >
                              {server.scope === 'system' ? '系统' : '用户'}
                            </Badge>
                            {isEnabled && (
                              <Badge
                                variant="outline"
                                className="border-green-600 text-xs text-green-600 dark:text-green-400"
                              >
                                <Check className="mr-1 h-3 w-3" />
                                已启用
                              </Badge>
                            )}
                          </div>
                          <p className="truncate font-mono text-xs text-muted-foreground">
                            {server.url}
                          </p>
                        </div>
                        <Switch
                          checked={isEnabled}
                          onCheckedChange={(checked) => {
                            handleToggleServer(server.id, checked)
                          }}
                          disabled={!!sessionId && updateMutation.isPending}
                          className="shrink-0"
                        />
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
            )}
          </section>

          {/* 底部统计与完成 */}
          <div className="flex shrink-0 items-center justify-between border-t pt-4 text-sm text-muted-foreground">
            <span>
              已启用 {enabledServerIds.size} / {allServers.length} 个 MCP 服务器
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setOpen(false)
              }}
              disabled={!!sessionId && updateMutation.isPending}
            >
              完成
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
