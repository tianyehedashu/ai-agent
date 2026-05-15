/**
 * AI Gateway · 调用日志（虚拟滚动）
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useVirtualizer, type VirtualItem } from '@tanstack/react-virtual'
import { ChevronDown } from 'lucide-react'

import { gatewayApi, type GatewayLogItem, type GatewayUsageAggregation } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

const PAGE_SIZE = 100

/** 表头与行共用，避免列宽漂移 */
const LOG_GRID_COLS = 'grid grid-cols-[150px_120px_112px_88px_72px_96px_80px_72px_minmax(0,1fr)]'

function credentialCellText(item: GatewayLogItem): string {
  const name = item.credential_name_snapshot?.trim()
  if (name) return name
  if (item.credential_id) return `${item.credential_id.slice(0, 8)}…`
  return '—'
}

function credentialCellTitle(item: GatewayLogItem): string | undefined {
  if (item.credential_name_snapshot?.trim() && item.credential_id) {
    return `${item.credential_name_snapshot.trim()} · ${item.credential_id}`
  }
  return item.credential_id ?? item.credential_name_snapshot ?? undefined
}

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
  const lastVisibleIndex =
    virtualItems.length > 0 ? (virtualItems[virtualItems.length - 1]?.index ?? -1) : -1

  useEffect(() => {
    if (items.length === 0 || !hasNextPage || isFetching) return
    if (lastVisibleIndex >= items.length - 1) {
      void fetchNextPage()
    }
  }, [lastVisibleIndex, items.length, hasNextPage, isFetching, fetchNextPage])

  const { data: detail } = useQuery({
    queryKey: ['gateway', 'log', selectedId, usageAggregation],
    queryFn: () => {
      if (typeof selectedId !== 'string' || selectedId.length === 0) {
        return Promise.reject(new Error('selectedId is required when query runs'))
      }
      return gatewayApi.getLog(selectedId, { usage_aggregation: usageAggregation })
    },
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
        <div
          className={`${LOG_GRID_COLS} border-b bg-muted/30 px-3 py-2 text-xs uppercase text-muted-foreground`}
        >
          <div>时间</div>
          <div>模型</div>
          <div>凭据</div>
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
                    className={`${LOG_GRID_COLS} items-center border-b px-3 text-left text-xs hover:bg-muted/30`}
                    type="button"
                    onClick={() => {
                      setSelectedId(item.id)
                    }}
                  >
                    <div className="truncate text-muted-foreground">
                      {new Date(item.created_at).toLocaleString()}
                    </div>
                    <div className="truncate font-mono">{item.real_model ?? '—'}</div>
                    <div className="truncate" title={credentialCellTitle(item)}>
                      {credentialCellText(item)}
                    </div>
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
        <SheetContent className="flex max-h-[100vh] flex-col sm:max-w-2xl">
          <SheetHeader className="shrink-0">
            <SheetTitle>请求详情</SheetTitle>
            <SheetDescription className="font-mono text-xs">{detail?.request_id}</SheetDescription>
          </SheetHeader>

          {selectedId !== null && detail === undefined ? (
            <p className="mt-4 text-sm text-muted-foreground">加载中...</p>
          ) : null}
          {detail !== undefined ? (
            <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1 text-xs">
              <dl className="grid grid-cols-[88px_1fr] gap-x-2 gap-y-2 rounded-md border bg-muted/20 p-3">
                <dt className="text-muted-foreground">凭据</dt>
                <dd className="min-w-0 break-words">
                  {detail.credential_name_snapshot?.trim() ?? '—'}
                  {detail.credential_id !== null && (
                    <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                      {detail.credential_id}
                    </div>
                  )}
                </dd>
                <dt className="text-muted-foreground">路由</dt>
                <dd className="font-mono">{detail.route_name ?? '—'}</dd>
                <dt className="text-muted-foreground">部署模型</dt>
                <dd className="break-words font-mono text-[11px]">
                  {detail.deployment_model_name ?? '—'}
                  {detail.deployment_gateway_model_id !== null &&
                    detail.deployment_gateway_model_id !== undefined && (
                      <div className="text-muted-foreground">
                        {detail.deployment_gateway_model_id}
                      </div>
                    )}
                </dd>
                <dt className="text-muted-foreground">提供商</dt>
                <dd>{detail.provider ?? '—'}</dd>
                <dt className="text-muted-foreground">虚拟 Key</dt>
                <dd className="break-words">
                  {detail.vkey_name_snapshot ?? '—'}
                  {detail.vkey_id !== null && (
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {detail.vkey_id}
                    </div>
                  )}
                </dd>
              </dl>

              <Collapsible defaultOpen className="group rounded-md border">
                <CollapsibleTrigger className="flex w-full items-center gap-2 px-2 py-2 text-left text-xs font-medium hover:bg-muted/40">
                  <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-data-[state=closed]:-rotate-90" />
                  Prompt（脱敏 / 详细日志）
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <pre className="max-h-56 overflow-auto border-t bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
                    {detail.prompt_redacted !== null && detail.prompt_redacted !== undefined
                      ? JSON.stringify(detail.prompt_redacted, null, 2)
                      : '（无）'}
                  </pre>
                </CollapsibleContent>
              </Collapsible>

              <Collapsible defaultOpen className="group rounded-md border">
                <CollapsibleTrigger className="flex w-full items-center gap-2 px-2 py-2 text-left text-xs font-medium hover:bg-muted/40">
                  <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-data-[state=closed]:-rotate-90" />
                  响应摘要
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <pre className="max-h-56 overflow-auto border-t bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
                    {detail.response_summary !== null && detail.response_summary !== undefined
                      ? JSON.stringify(detail.response_summary, null, 2)
                      : '（无）'}
                  </pre>
                </CollapsibleContent>
              </Collapsible>

              <Collapsible className="group rounded-md border">
                <CollapsibleTrigger className="flex w-full items-center gap-2 px-2 py-2 text-left text-xs font-medium hover:bg-muted/40">
                  <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-data-[state=closed]:-rotate-90" />
                  快照与元数据
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <pre className="max-h-48 overflow-auto border-t bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
                    {JSON.stringify(
                      {
                        team_snapshot: detail.team_snapshot,
                        route_snapshot: detail.route_snapshot,
                        metadata_extra: detail.metadata_extra,
                      },
                      null,
                      2
                    )}
                  </pre>
                </CollapsibleContent>
              </Collapsible>

              <Collapsible className="group rounded-md border">
                <CollapsibleTrigger className="flex w-full items-center gap-2 px-2 py-2 text-left text-xs font-medium hover:bg-muted/40">
                  <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-data-[state=closed]:-rotate-90" />
                  完整 JSON（复制用）
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <pre className="max-h-64 overflow-auto border-t bg-muted p-2 font-mono text-[11px] leading-relaxed">
                    {JSON.stringify(detail, null, 2)}
                  </pre>
                </CollapsibleContent>
              </Collapsible>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  )
}
