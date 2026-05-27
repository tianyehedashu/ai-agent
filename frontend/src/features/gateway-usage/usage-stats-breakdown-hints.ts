import type { UsageStatisticsBreakdownResponse } from '@/api/gateway/stats'

export function credentialBreakdownFooterHints(
  data: UsageStatisticsBreakdownResponse,
  requestedTopN: number
): readonly string[] {
  const hints: string[] = []
  const listedRequests = data.items.reduce((sum, slice) => sum + slice.requests, 0)
  const unassigned = data.parent_requests - listedRequests

  if (unassigned > 0) {
    hints.push(`${unassigned.toLocaleString()} 次请求未关联凭据`)
  }
  if (data.items.length >= requestedTopN) {
    hints.push(`已展示用量最高的前 ${requestedTopN.toString()} 个凭据，更多请点「分布」`)
  }
  return hints
}
