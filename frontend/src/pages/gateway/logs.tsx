/**
 * AI Gateway · 调用日志（虚拟滚动）
 */

import { useMemo, useRef, useState } from 'react'

import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useVirtualizer, type VirtualItem } from '@tanstack/react-virtual'

import { gatewayApi, type GatewayLogItem, type GatewayUsageAggregation } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

const PAGE_SIZE = 100

export default function GatewayLogsPage(): React.JSX.Element {
  const parentRef = useRef<HTMLDivElement>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [usageAggregation, setUsageAggregation] = useState<GatewayUsageAggregation>('user')

  const { data, fetchNextPage, hasNextPage, isFetching, isLoading } = useInfiniteQuery({
    queryKey: ['gateway', 'logs', usageAggregation],
    initialPageParam: 1,
    queryFn: ({ pageParam }: { pageParam: number }) =>
      gatewayApi.listLogs({
        usage_aggregation: usageAggregation,
        page: pageParam,
        page_size: PAGE_SIZE,
      }),
    getNextPageParam: (lastPage, all) => {
      const fetched = all.reduce((sum, p) => sum + p.items.length, 0)
      return fetched < lastPage.total ? all.length + 1 : undefined
    },
  })

  const items = useMemo<GatewayLogItem[]>(() => data?.pages.flatMap((p) => p.items) ?? [], [data])

  const virtualizer = useVirtualizer({
    count: items.length + (hasNextPage ? 1 : 0),
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 8,
  })

  const virtualItems = virtualizer.getVirtualItems()
  const lastItem = virtualItems.at(-1)
  if (lastItem !== undefined && lastItem.index >= items.length - 1 && hasNextPage && !isFetching) {
    void fetchNextPage()
  }

  const { data: detail } = useQuery({
    queryKey: ['gateway', 'log', selectedId, usageAggregation],
    queryFn: () =>
      selectedId ? gatewayApi.getLog(selectedId, { usage_aggregation: usageAggregation }) : null,
    enabled: !!selectedId,
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">调用日志</h2>
          <p className="text-sm text-muted-foreground">
            按月分区表 + 虚拟滚动，最近 {items.length.toLocaleString()} 条
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-md border bg-background p-0.5">
          {(['user', 'workspace'] as const).map((value) => (
            <Button
              key={value}
              size="sm"
              variant={usageAggregation === value ? 'default' : 'ghost'}
              className="h-7 px-3 text-xs"
              onClick={() => {
                setUsageAggregation(value)
                setSelectedId(null)
              }}
            >
              {value === 'user' ? '按账号' : '当前工作区'}
            </Button>
          ))}
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="grid grid-cols-[160px_140px_120px_80px_120px_100px_100px_1fr] border-b bg-muted/30 px-3 py-2 text-xs uppercase text-muted-foreground">
          <div>时间</div>
          <div>模型</div>
          <div>能力</div>
          <div>状态</div>
          <div>Tokens</div>
          <div>成本</div>
          <div>延迟</div>
          <div>请求 ID</div>
        </div>
        <div ref={parentRef} className="h-[560px] overflow-auto">
          {isLoading ? (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">加载中...</div>
          ) : items.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">暂无日志</div>
          ) : (
            <div
              style={{
                height: `${virtualizer.getTotalSize().toString()}px`,
                width: '100%',
                position: 'relative',
              }}
            >
              {virtualItems.map((row: VirtualItem) => {
                if (row.index >= items.length) {
                  return (
                    <div
                      key={row.key}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: `${row.size.toString()}px`,
                        transform: `translateY(${row.start.toString()}px)`,
                      }}
                      className="px-3 py-2 text-center text-xs text-muted-foreground"
                    >
                      加载更多...
                    </div>
                  )
                }
                const item = row.index < items.length ? items[row.index] : undefined
                if (item === undefined) return null
                return (
                  <button
                    key={row.key}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: `${row.size.toString()}px`,
                      transform: `translateY(${row.start.toString()}px)`,
                    }}
                    className="grid grid-cols-[160px_140px_120px_80px_120px_100px_100px_1fr] items-center border-b px-3 text-left text-xs hover:bg-muted/30"
                    onClick={() => {
                      setSelectedId(item.id)
                    }}
                  >
                    <div className="truncate text-muted-foreground">
                      {new Date(item.created_at).toLocaleString()}
                    </div>
                    <div className="truncate font-mono">{item.real_model ?? '—'}</div>
                    <div className="truncate">{item.capability}</div>
                    <div>
                      <span
                        className={
                          item.status === 'success'
                            ? 'text-emerald-500'
                            : item.status === 'error'
                              ? 'text-destructive'
                              : 'text-amber-500'
                        }
                      >
                        {item.status}
                      </span>
                    </div>
                    <div className="tabular-nums">
                      {(item.input_tokens + item.output_tokens).toLocaleString()}
                    </div>
                    <div className="tabular-nums">${Number(item.cost_usd).toFixed(5)}</div>
                    <div className="tabular-nums">{item.latency_ms}ms</div>
                    <div className="truncate font-mono text-muted-foreground">
                      {item.request_id ?? item.id}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 border-t px-3 py-2 text-xs text-muted-foreground">
          {hasNextPage && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void fetchNextPage()}
              disabled={isFetching}
            >
              {isFetching ? '加载中...' : '加载更多'}
            </Button>
          )}
        </div>
      </Card>

      <Sheet
        open={!!selectedId}
        onOpenChange={(v) => {
          if (!v) setSelectedId(null)
        }}
      >
        <SheetContent className="sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>请求详情</SheetTitle>
            <SheetDescription className="font-mono text-xs">{detail?.request_id}</SheetDescription>
          </SheetHeader>
          <pre className="mt-4 max-h-[80vh] overflow-auto rounded bg-muted p-3 text-xs">
            {detail ? JSON.stringify(detail, null, 2) : 'Loading...'}
          </pre>
        </SheetContent>
      </Sheet>
    </div>
  )
}
