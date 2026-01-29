/**
 * 系统 MCP（客户端直连）查看与配置页
 *
 * 展示由平台暴露的 Streamable HTTP MCP 服务器（如 llm-server / ai-agent-llm），
 * 提供 Cursor mcp.json 配置的复制与下载。
 */

import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Copy, Download, Server } from 'lucide-react'
import { toast } from 'sonner'

import { mcpApi } from '@/api/mcp'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type {
  ClientDirectMCPServer,
  ClientMCPConfigResponse,
  CursorMCPServerConfig,
} from '@/types/mcp'

/** 后端 scope 与 Cursor mcp.json 中常用 key 的对应（与后端 _SCOPE_TO_CURSOR_NAME 一致） */
const SCOPE_TO_CURSOR_NAME: Record<string, string> = {
  'llm-server': 'ai-agent-llm',
}

function scopeToCursorName(scope: string): string {
  return SCOPE_TO_CURSOR_NAME[scope] ?? scope.replace(/-/g, '_')
}

function copyToClipboard(text: string): void {
  void navigator.clipboard.writeText(text).then(() => {
    toast.success('已复制到剪贴板')
  })
}

function downloadJson(filename: string, obj: object): void {
  const blob = new Blob([JSON.stringify(obj, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  toast.success(`已下载 ${filename}`)
}

interface ServerConfigCardProps {
  server: ClientDirectMCPServer
  config: CursorMCPServerConfig
  cursorName: string
}

function ServerConfigCard({ server, config, cursorName }: ServerConfigCardProps): React.JSX.Element {
  const snippet = { [cursorName]: config }
  const snippetJson = JSON.stringify(snippet, null, 2)
  const tools = server.tools ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Server className="h-5 w-5" />
          {server.name}
        </CardTitle>
        <CardDescription>{server.description}</CardDescription>
        <p className="text-sm text-muted-foreground">
          工具数量: {server.tool_count} · 传输: Streamable HTTP
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {tools.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">可用工具</p>
            <TooltipProvider delayDuration={200}>
              <ul className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto rounded-md border bg-muted/30 p-2 text-sm">
                {tools.map((t) => (
                  <li key={t.name}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="cursor-default rounded bg-muted/80 px-2 py-0.5 font-mono text-xs font-medium hover:bg-muted">
                          {t.name}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-xs">
                        {t.description ?? '无描述'}
                      </TooltipContent>
                    </Tooltip>
                  </li>
                ))}
              </ul>
            </TooltipProvider>
          </div>
        )}
        <div>
          <p className="mb-2 text-sm font-medium">Cursor mcp.json 配置片段</p>
          <pre className="max-h-48 overflow-auto rounded-md border bg-muted/50 p-3 text-xs">
            <code>{snippetJson}</code>
          </pre>
          <div className="mt-2 flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(snippetJson)}
              className="gap-1"
            >
              <Copy className="h-4 w-4" />
              复制
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadJson(`mcp-${cursorName}.json`, snippet)}
              className="gap-1"
            >
              <Download className="h-4 w-4" />
              下载片段
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function SystemMCPPage(): React.JSX.Element {
  const {
    data: listData,
    isLoading: listLoading,
    error: listError,
  } = useQuery({
    queryKey: ['mcp-client-direct-servers'],
    queryFn: () => mcpApi.listClientDirectServers(),
  })

  const { data: configData } = useQuery({
    queryKey: ['mcp-client-config'],
    queryFn: () => mcpApi.getClientConfig(),
  })

  const servers = listData?.servers ?? []
  const mcpServers = (configData as ClientMCPConfigResponse | undefined)?.mcpServers ?? {}

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">系统 MCP（客户端直连）</h1>
        <p className="mt-2 text-muted-foreground">
          由平台暴露的 Streamable HTTP MCP 服务，Cursor 等客户端可通过 mcp.json 直连并调用工具。
        </p>
      </div>

      <Alert className="mb-6">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          将下方配置填入 <code className="rounded bg-muted px-1">~/.cursor/mcp.json</code> 或项目
          <code className="rounded bg-muted px-1">.cursor/mcp.json</code>
          ，并将 <code className="rounded bg-muted px-1">&lt;YOUR_API_KEY&gt;</code> 替换为具有
          <code className="rounded bg-muted px-1">mcp:llm-server</code> 权限的 API Key。
        </AlertDescription>
      </Alert>

      {listError && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>加载系统 MCP 列表失败，请稍后重试</AlertDescription>
        </Alert>
      )}

      {listLoading ? (
        <div className="flex justify-center py-12 text-muted-foreground">加载中...</div>
      ) : servers.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
          <Server className="mb-4 h-12 w-12 text-muted-foreground" />
          <p className="text-muted-foreground">暂无客户端直连的 MCP 服务</p>
        </div>
      ) : (
        <>
          <div className="mb-4 flex justify-end">
            <Button
              variant="outline"
              onClick={() => downloadJson('mcp.json', { mcpServers })}
              className="gap-1"
            >
              <Download className="h-4 w-4" />
              下载完整 mcp.json
            </Button>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {servers.map((server) => {
              const cursorName = scopeToCursorName(server.scope)
              const config = mcpServers[cursorName]
              if (!config) return null
              return (
                <ServerConfigCard
                  key={server.scope}
                  server={server}
                  config={config}
                  cursorName={cursorName}
                />
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
