import { useMemo } from 'react'
import type React from 'react'

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import {
  statsApi,
  type GatewayUsageStatsGroupBy,
  type GatewayUsageStatsItem,
  type UsageStatisticsBreakdownResponse,
} from '@/api/gateway/stats'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { UsageStatsBreakdownList } from '@/features/gateway-usage/usage-stats-breakdown-list'
import type { UsageStatsBreakdownBaseQuery } from '@/features/gateway-usage/use-usage-stats-breakdown-batch'
import { ExternalLink } from '@/lib/lucide-icons'
import { buildFilterKey } from '@/lib/pagination'

const DETAIL_TOP_N = 10

interface DetailBreakdownBundle {
  credential?: UsageStatisticsBreakdownResponse
  model?: UsageStatisticsBreakdownResponse
}

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

function detailBreakdownQueryKey(
  teamId: string,
  baseQuery: UsageStatsBreakdownBaseQuery,
  parentGroupBy: GatewayUsageStatsGroupBy,
  parentGroupKey: string,
  topN: number,
  fetchCredential: boolean,
  fetchModel: boolean
): readonly (string | number | boolean)[] {
  return [
    'gateway',
    'usage-stats-detail-breakdown',
    teamId,
    buildFilterKey([
      baseQuery.days ?? 7,
      baseQuery.usage_aggregation ?? 'workspace',
      baseQuery.credential_id ?? '',
      baseQuery.user_id ?? '',
      baseQuery.team_id ?? '',
      baseQuery.model ?? '',
      baseQuery.provider ?? '',
      baseQuery.capability ?? '',
      baseQuery.status ?? '',
      baseQuery.vkey_id ?? '',
    ]),
    parentGroupBy,
    parentGroupKey,
    topN,
    fetchCredential,
    fetchModel,
  ] as const
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
  const parentKey = item?.group_key.trim() ?? ''
  const showCredentialBreakdown = groupBy !== 'credential'
  const showModelBreakdown = groupBy !== 'model'
  const fetchEnabled = sheetOpen && parentKey.length > 0

  const { data, isLoading, isError } = useQuery({
    queryKey: detailBreakdownQueryKey(
      teamId,
      baseQuery,
      groupBy,
      parentKey,
      DETAIL_TOP_N,
      showCredentialBreakdown,
      showModelBreakdown
    ),
    queryFn: async (): Promise<DetailBreakdownBundle> => {
      const shared = {
        ...baseQuery,
        parent_group_by: groupBy,
        parent_group_key: parentKey,
        top_n: DETAIL_TOP_N,
      }
      const [credential, model] = await Promise.all([
        showCredentialBreakdown
          ? statsApi.usageStatsBreakdown(teamId, {
              ...shared,
              breakdown_by: 'credential',
            })
          : Promise.resolve(undefined),
        showModelBreakdown
          ? statsApi.usageStatsBreakdown(teamId, {
              ...shared,
              breakdown_by: 'model',
            })
          : Promise.resolve(undefined),
      ])
      return { credential, model }
    },
    enabled: fetchEnabled,
    staleTime: 60_000,
  })

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
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground">凭据分布</h4>
                {isError ? <p className="text-sm text-destructive">加载失败</p> : null}
                <UsageStatsBreakdownList
                  data={data?.credential}
                  loading={isLoading}
                  variant="sheet"
                />
              </div>
            ) : null}
            {showModelBreakdown ? (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground">模型分布</h4>
                {isError ? <p className="text-sm text-destructive">加载失败</p> : null}
                <UsageStatsBreakdownList data={data?.model} loading={isLoading} variant="sheet" />
              </div>
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
