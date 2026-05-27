import { useMemo } from 'react'
import type React from 'react'

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import {
  statsApi,
  type GatewayUsageStatsGroupBy,
  type GatewayUsageStatsItem,
} from '@/api/gateway/stats'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  usageStatsBreakdownQueryKey,
  type UsageStatsBreakdownBaseQuery,
} from '@/features/gateway-usage/use-usage-stats-breakdown-batch'
import { ExternalLink } from '@/lib/lucide-icons'

const DETAIL_TOP_N = 10

interface UsageStatsDetailSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  teamId: string
  groupBy: GatewayUsageStatsGroupBy
  item: GatewayUsageStatsItem | null
  baseQuery: UsageStatsBreakdownBaseQuery
  sheetOpen: boolean
  logsNavigationState: Record<string, string | undefined>
}

function BreakdownList({
  title,
  teamId,
  baseQuery,
  parentGroupBy,
  parentGroupKey,
  breakdownBy,
  sheetOpen,
}: Readonly<{
  title: string
  teamId: string
  baseQuery: UsageStatsBreakdownBaseQuery
  parentGroupBy: GatewayUsageStatsGroupBy
  parentGroupKey: string
  breakdownBy: 'credential' | 'model'
  sheetOpen: boolean
}>): React.JSX.Element {
  const enabled = sheetOpen && parentGroupKey.trim().length > 0
  const { data, isLoading, isError } = useQuery({
    queryKey: usageStatsBreakdownQueryKey(
      teamId,
      baseQuery,
      parentGroupBy,
      parentGroupKey,
      breakdownBy,
      DETAIL_TOP_N
    ),
    queryFn: () =>
      statsApi.usageStatsBreakdown(teamId, {
        ...baseQuery,
        parent_group_by: parentGroupBy,
        parent_group_key: parentGroupKey,
        breakdown_by: breakdownBy,
        top_n: DETAIL_TOP_N,
      }),
    enabled,
    staleTime: 60_000,
  })

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-muted-foreground">{title}</h4>
      {isLoading ? <p className="text-sm text-muted-foreground">加载中…</p> : null}
      {isError ? <p className="text-sm text-destructive">加载失败</p> : null}
      {!isLoading && !isError && (data?.items.length ?? 0) === 0 ? (
        <p className="text-sm text-muted-foreground">暂无数据</p>
      ) : null}
      {data && data.items.length > 0 ? (
        <ul className="space-y-2 text-sm">
          {data.items.map((slice) => (
            <li
              key={`${breakdownBy}-${slice.group_key}`}
              className="flex items-center justify-between gap-2 border-b border-dashed pb-2 last:border-0"
            >
              <span className="min-w-0 truncate font-medium" title={slice.label}>
                {slice.label}
              </span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {slice.requests.toLocaleString()}（{(slice.share * 100).toFixed(1)}%）
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

export function UsageStatsDetailSheet({
  open,
  onOpenChange,
  teamId,
  groupBy,
  item,
  baseQuery,
  sheetOpen,
  logsNavigationState,
}: Readonly<UsageStatsDetailSheetProps>): React.JSX.Element {
  const parentKey = item?.group_key ?? ''
  const showCredentialBreakdown = groupBy !== 'credential'
  const showModelBreakdown = groupBy !== 'model'

  const logsHref = useMemo(() => `/gateway/teams/${teamId}/logs`, [teamId])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="pr-8 text-base">{item?.label ?? '分布详情'}</SheetTitle>
          <SheetDescription>
            {item
              ? `${item.requests.toLocaleString()} 次请求 · ${item.total_tokens.toLocaleString()} tokens`
              : '选择一行查看凭据与模型分布'}
          </SheetDescription>
        </SheetHeader>
        {item ? (
          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto py-2">
            {showCredentialBreakdown ? (
              <BreakdownList
                title="凭据分布"
                teamId={teamId}
                baseQuery={baseQuery}
                parentGroupBy={groupBy}
                parentGroupKey={parentKey}
                breakdownBy="credential"
                sheetOpen={sheetOpen}
              />
            ) : null}
            {showModelBreakdown ? (
              <BreakdownList
                title="模型分布"
                teamId={teamId}
                baseQuery={baseQuery}
                parentGroupBy={groupBy}
                parentGroupKey={parentKey}
                breakdownBy="model"
                sheetOpen={sheetOpen}
              />
            ) : null}
            <Button variant="outline" size="sm" className="w-full gap-2" asChild>
              <Link to={logsHref} state={{ usageStatsFilters: logsNavigationState }}>
                <ExternalLink className="h-4 w-4" />
                在调用日志中查看
              </Link>
            </Button>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
