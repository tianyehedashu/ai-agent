/**
 * SessionNotice - 会话重建通知组件
 *
 * 当用户的沙箱环境被清理后重新发送消息时，显示友好的提示，
 * 告知用户之前安装的包和创建的文件可能需要重新配置。
 */

import { AlertTriangle, Package, FileText, X, Clock, RefreshCw } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { SessionRecreationData } from '@/types'

interface SessionNoticeProps {
  data: SessionRecreationData
  onDismiss: () => void
}

/** 清理原因的友好描述 */
function getCleanupReasonText(reason: string): string {
  const reasonMap: Record<string, string> = {
    idle_timeout: '由于长时间未活动',
    disconnect_timeout: '由于连接断开',
    task_complete: '由于任务已完成',
    resource_limit: '由于资源限制',
    app_shutdown: '由于服务维护',
    user_request: '应您的要求',
    error: '由于发生错误',
  }
  return reasonMap[reason] || '由于系统优化'
}

/** 格式化时间 */
function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMinutes = Math.floor(diffMs / 60000)

    if (diffMinutes < 1) return '刚刚'
    if (diffMinutes < 60) return `${String(diffMinutes)} 分钟前`
    const diffHours = Math.floor(diffMinutes / 60)
    if (diffHours < 24) return `${String(diffHours)} 小时前`
    const diffDays = Math.floor(diffHours / 24)
    return `${String(diffDays)} 天前`
  } catch {
    return '之前'
  }
}

export function SessionNotice({
  data,
  onDismiss,
}: Readonly<SessionNoticeProps>): React.JSX.Element | null {
  const { previousState, message } = data

  // 如果没有历史状态或不是重建，不显示
  if (!previousState) {
    return null
  }

  const { cleanedAt, cleanupReason, packagesInstalled, filesCreated, commandCount } = previousState

  const hasPackages = packagesInstalled.length > 0
  const hasFiles = filesCreated.length > 0
  const cleanupReasonText = getCleanupReasonText(cleanupReason)
  const timeText = formatTime(cleanedAt)

  return (
    <Card
      className={cn(
        'relative mx-auto mb-4 max-w-2xl overflow-hidden',
        'border-amber-500/30 bg-gradient-to-r from-amber-500/5 to-orange-500/5',
        'animate-in fade-in slide-in-from-top-2 duration-300'
      )}
    >
      {/* 关闭按钮 */}
      <button
        type="button"
        onClick={onDismiss}
        className={cn(
          'absolute right-2 top-2 rounded-full p-1',
          'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
          'transition-colors'
        )}
        aria-label="关闭通知"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="p-4 pr-10">
        {/* 标题区域 */}
        <div className="mb-3 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-500/20">
            <RefreshCw className="h-4 w-4 text-amber-500" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">运行环境已重建</h3>
            <p className="text-xs text-muted-foreground">
              {cleanupReasonText}，{timeText}您的沙箱环境被清理
            </p>
          </div>
        </div>

        {/* 自定义消息 */}
        {message && (
          <p className="mb-3 text-xs text-muted-foreground">
            <AlertTriangle className="mr-1 inline-block h-3 w-3 text-amber-500" />
            {message}
          </p>
        )}

        {/* 需要重新配置的内容 */}
        {(hasPackages || hasFiles) && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">以下内容可能需要重新配置：</p>

            {/* 已安装的包 */}
            {hasPackages && (
              <div className="flex items-start gap-2 rounded-md bg-muted/30 px-3 py-2">
                <Package className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue-500" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-foreground">已安装的包</p>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {packagesInstalled.slice(0, 5).join(', ')}
                    {packagesInstalled.length > 5 && ` 等 ${String(packagesInstalled.length)} 个包`}
                  </p>
                </div>
              </div>
            )}

            {/* 已创建的文件 */}
            {hasFiles && (
              <div className="flex items-start gap-2 rounded-md bg-muted/30 px-3 py-2">
                <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-foreground">已创建的文件</p>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {filesCreated.slice(0, 5).join(', ')}
                    {filesCreated.length > 5 && ` 等 ${String(filesCreated.length)} 个文件`}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 统计信息 */}
        {commandCount > 0 && (
          <div className="mt-3 flex items-center gap-1 text-[10px] text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>之前执行了 {String(commandCount)} 条命令</span>
          </div>
        )}

        {/* 提示 */}
        <div className="mt-3 rounded-md bg-blue-500/10 px-3 py-2">
          <p className="text-[11px] text-blue-600 dark:text-blue-400">
            💡 提示：您可以通过发送命令重新安装需要的包或创建文件。对话历史已保留。
          </p>
        </div>
      </div>
    </Card>
  )
}
