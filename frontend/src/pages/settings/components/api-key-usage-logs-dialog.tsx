/**
 * API Key 使用日志对话框
 */

import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { apiKeyApi } from '@/api/api-key'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { formatRelativeTime } from '@/lib/utils'

interface ApiKeyUsageLogsDialogProps {
  apiKeyId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ApiKeyUsageLogsDialog({
  apiKeyId,
  open,
  onOpenChange,
}: ApiKeyUsageLogsDialogProps): React.ReactElement {
  const { data: logs, isLoading } = useQuery({
    queryKey: ['api-key-logs', apiKeyId],
    queryFn: () => apiKeyApi.getUsageLogs(apiKeyId),
    enabled: open,
  })

  const getStatusColor = (status: number): string => {
    if (status >= 200 && status < 300) return 'text-green-600'
    if (status >= 300 && status < 400) return 'text-yellow-600'
    if (status >= 400 && status < 500) return 'text-orange-600'
    return 'text-red-600'
  }

  const getMethodBadgeVariant = (method: string): 'default' | 'secondary' | 'outline' | 'destructive' => {
    switch (method.toLowerCase()) {
      case 'get':
        return 'default'
      case 'post':
        return 'secondary'
      case 'put':
      case 'patch':
        return 'outline'
      case 'delete':
        return 'destructive'
      default:
        return 'outline'
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>API Key 使用日志</DialogTitle>
          <DialogDescription>{logs?.length ?? 0} 条记录</DialogDescription>
        </DialogHeader>

        <ScrollArea className="h-[500px]">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-muted-foreground">加载中...</div>
            </div>
          ) : !logs || logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground">暂无使用记录</p>
            </div>
          ) : (
            <div className="space-y-2">
              {logs.map((log) => (
                <LogEntry key={log.id} log={log} />
              ))}
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}

function LogEntry({ log }: { log: { endpoint: string; method: string; ip_address?: string; status_code: number; response_time_ms?: number; created_at: string; id?: string } }): React.ReactElement {
  const getStatusColor = (status: number): string => {
    if (status >= 200 && status < 300) return 'text-green-600'
    if (status >= 300 && status < 400) return 'text-yellow-600'
    if (status >= 400 && status < 500) return 'text-orange-600'
    return 'text-red-600'
  }

  const getMethodBadgeVariant = (method: string): 'default' | 'secondary' | 'outline' | 'destructive' => {
    switch (method.toLowerCase()) {
      case 'get':
        return 'default'
      case 'post':
        return 'secondary'
      case 'put':
      case 'patch':
        return 'outline'
      case 'delete':
        return 'destructive'
      default:
        return 'outline'
    }
  }

  return (
    <div className="rounded-lg border p-3 text-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={getMethodBadgeVariant(log.method)} className="text-xs">
            {log.method}
          </Badge>
          <code className="text-xs">{log.endpoint}</code>
        </div>
        <Badge variant="outline" className={getStatusColor(log.status_code)}>
          {log.status_code}
        </Badge>
      </div>

      <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
        <span>{formatRelativeTime(log.created_at)}</span>
        {log.response_time_ms && <span>{log.response_time_ms}ms</span>}
        {log.ip_address && <span>IP: {log.ip_address}</span>}
      </div>
    </div>
  )
}
