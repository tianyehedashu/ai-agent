import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { formatRateLine } from '@/features/gateway-pricing/format'
import { useUserPreferenceStore } from '@/stores/user-preference'

export default function GatewayPricingDownstreamPage(): React.JSX.Element {
  const currency = useUserPreferenceStore((s) => s.displayCurrency)
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['gateway-pricing-downstream', currency],
    queryFn: () => gatewayApi.listDownstreamPricing({ scope: 'team', currency }),
  })

  const syncMut = useMutation({
    mutationFn: () => gatewayApi.syncDownstreamPricing({ scope: 'team' }),
    onSuccess: (report) => {
      toast.success(`已同步：新增 ${String(report.created)}，跳过 ${String(report.skipped)}`)
      void qc.invalidateQueries({ queryKey: ['gateway-pricing-downstream'] })
      void qc.invalidateQueries({ queryKey: ['gateway-pricing-my'] })
    },
    onError: () => {
      toast.error('同步失败')
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button
          type="button"
          onClick={() => {
            syncMut.mutate()
          }}
          disabled={syncMut.isPending}
        >
          ⟳ 一键同步上游
        </Button>
        <span className="text-xs text-muted-foreground">为尚未覆盖的模型创建「跟随上游」售价</span>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-muted-foreground">
              <tr>
                <th className="px-3 py-2">模型 ID</th>
                <th className="px-3 py-2">策略</th>
                <th className="px-3 py-2">生效价</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((row) => (
                <tr key={row.id} className="cv-auto-row border-t">
                  <td className="px-3 py-2 font-mono text-xs">{row.gateway_model_id ?? '默认'}</td>
                  <td className="px-3 py-2">
                    {row.inheritance_strategy === 'mirror' ? '跟随上游' : '自定义'}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.inheritance_strategy === 'mirror'
                      ? '= 上游'
                      : formatRateLine(
                          row.input_cost_per_million_display,
                          row.output_cost_per_million_display,
                          currency
                        )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
