/**
 * MCP 服务器卡片组件（占位实现，待后续完善）
 */

import { MoreVertical, Trash2, Edit, TestTube } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Switch } from '@/components/ui/switch'
import type { MCPServerConfig } from '@/types/mcp'

interface MCPServerCardProps {
  server: MCPServerConfig
}

export function MCPServerCard({ server }: MCPServerCardProps): React.JSX.Element {
  const displayName = server.display_name ?? server.name

  const getStatusColor = (): string => {
    switch (server.status_color) {
      case 'green':
        return 'bg-green-500'
      case 'red':
        return 'bg-red-500'
      case 'yellow':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getStatusText = (): string => {
    return server.status_text ?? '未知'
  }

  return (
    <Card className="group relative overflow-hidden transition-all hover:shadow-md">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg">{displayName}</CardTitle>
              <Badge
                variant={server.scope === 'system' ? 'default' : 'secondary'}
                className="text-xs"
              >
                {server.scope === 'system' ? '系统' : '用户'}
              </Badge>
            </div>
            <CardDescription className="mt-1">{server.url}</CardDescription>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 opacity-0 group-hover:opacity-100"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>
                <TestTube className="mr-2 h-4 w-4" />
                测试连接
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Edit className="mr-2 h-4 w-4" />
                编辑
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive">
                <Trash2 className="mr-2 h-4 w-4" />
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* 状态指示 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${getStatusColor()}`} />
            <span className="text-sm text-muted-foreground">{getStatusText()}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">启用</span>
            <Switch checked={server.enabled} disabled />
          </div>
        </div>

        {/* 环境类型 */}
        <div className="rounded-md bg-muted px-3 py-2 text-xs">
          <span className="text-muted-foreground">环境: </span>
          <span className="font-mono">{server.env_type}</span>
        </div>
      </CardContent>
    </Card>
  )
}
