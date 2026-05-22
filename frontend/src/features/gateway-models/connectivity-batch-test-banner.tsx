import { memo } from 'react'

import { Button } from '@/components/ui/button'
import { Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import type { ConnectivityBatchTestState } from './hooks/use-connectivity-batch-test'

interface ConnectivityBatchTestBannerProps {
  state: ConnectivityBatchTestState
  onRetestFailed: () => void
  onScrollToFirstFailed?: () => void
  className?: string
}

export const ConnectivityBatchTestBanner = memo(function ConnectivityBatchTestBanner({
  state,
  onRetestFailed,
  onScrollToFirstFailed,
  className,
}: ConnectivityBatchTestBannerProps): React.JSX.Element | null {
  const { running, total, done, failedIds, includesVideoProbe, cancel } = state

  if (!running && failedIds.length === 0) {
    return null
  }

  return (
    <div
      role="status"
      className={cn(
        'sticky top-0 z-20 flex flex-wrap items-center gap-2 rounded-lg border bg-card/95 px-3 py-2 text-sm shadow-sm backdrop-blur-sm',
        className
      )}
    >
      {running ? (
        <>
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
          <span className="tabular-nums">
            测试中 {done}/{total}
          </span>
          {failedIds.length > 0 ? (
            <span className="text-xs text-rose-600 dark:text-rose-400">
              · 已失败 {failedIds.length}
            </span>
          ) : null}
          {includesVideoProbe ? (
            <span className="text-xs text-muted-foreground">· 含视频模型，单条探活可能较慢</span>
          ) : null}
        </>
      ) : (
        <span>
          测试完成 · 失败{' '}
          <span className="tabular-nums text-rose-600 dark:text-rose-400">{failedIds.length}</span>{' '}
          / {total}
        </span>
      )}
      <div className="ml-auto flex flex-wrap gap-1">
        {running ? (
          <Button type="button" size="sm" variant="ghost" className="h-7 text-xs" onClick={cancel}>
            取消
          </Button>
        ) : null}
        {!running && failedIds.length > 0 && onScrollToFirstFailed ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 text-xs"
            onClick={onScrollToFirstFailed}
          >
            查看首个失败
          </Button>
        ) : null}
        {!running && failedIds.length > 0 ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="h-7 text-xs"
            onClick={onRetestFailed}
          >
            重测失败 ({failedIds.length})
          </Button>
        ) : null}
      </div>
    </div>
  )
})
