import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { formatRateLine } from '@/features/gateway-pricing/format'
import { useUserPreferenceStore } from '@/stores/user-preference'

export default function GatewayPricingMyPricesPage(): React.JSX.Element {
  const currency = useUserPreferenceStore((s) => s.displayCurrency)
  const { data, isLoading } = useQuery({
    queryKey: ['gateway-pricing-my', currency],
    queryFn: () => gatewayApi.listMyPrices({ currency }),
  })

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">加载中…</p>
  }

  const rows = data ?? []
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">暂无定价数据，请联系管理员配置上游成本。</p>
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-left text-muted-foreground">
          <tr>
            <th className="px-3 py-2">模型</th>
            <th className="px-3 py-2">单价（/ 1M tokens）</th>
            <th className="px-3 py-2">来源</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.gateway_model_id ?? row.model_name} className="cv-auto-row border-t">
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
          ))}
        </tbody>
      </table>
    </div>
  )
}
