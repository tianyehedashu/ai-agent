import type React from 'react'
import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { formatRateLine } from '@/features/gateway-pricing/format'
import { PricingTable, type PricingTableColumn } from '@/features/gateway-pricing/pricing-table'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { cn } from '@/lib/utils'

const columns: readonly PricingTableColumn[] = [
  { key: 'model', label: '模型', className: 'px-3 py-2' },
  { key: 'rate', label: '单价（/ 1M tokens）', className: 'px-3 py-2' },
  { key: 'source', label: '来源', className: 'px-3 py-2' },
]

export default function GatewayPricingMyPricesPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const currency = GATEWAY_DISPLAY_CURRENCY
  const [searchParams] = useSearchParams()
  const targetModel = searchParams.get('model')?.trim() ?? ''
  const pricesQuery = useQuery({
    queryKey: ['gateway-pricing-my', teamId, currency],
    queryFn: () => gatewayApi.listMyPrices(teamId, { currency }),
  })

  const rows = useMemo(() => {
    const raw = pricesQuery.data ?? []
    if (!targetModel) return raw
    return [...raw].sort((left, right) => {
      const leftHit = left.model_name === targetModel || left.gateway_model_id === targetModel
      const rightHit = right.model_name === targetModel || right.gateway_model_id === targetModel
      if (leftHit === rightHit) return 0
      return leftHit ? -1 : 1
    })
  }, [pricesQuery.data, targetModel])

  return (
    <PricingTable
      columns={columns}
      loading={pricesQuery.isLoading}
      error={pricesQuery.isError}
      empty={rows.length === 0}
      onRetry={() => {
        void pricesQuery.refetch()
      }}
    >
      {rows.map((row) => {
        const highlighted =
          Boolean(targetModel) &&
          (row.model_name === targetModel || row.gateway_model_id === targetModel)
        return (
          <tr
            key={row.gateway_model_id ?? row.model_name}
            className={cn('cv-auto-row border-t', highlighted ? 'bg-primary/5' : undefined)}
          >
            <td className="px-3 py-2 font-mono">{row.model_name}</td>
            <td className="px-3 py-2 tabular-nums">
              {formatRateLine(
                row.input_cost_per_million_display,
                row.output_cost_per_million_display,
                currency
              )}
            </td>
            <td className="px-3 py-2 text-muted-foreground">
              {row.inheritance_strategy === 'mirror' ? '跟随上游' : '团队覆盖'}
            </td>
          </tr>
        )
      })}
    </PricingTable>
  )
}
