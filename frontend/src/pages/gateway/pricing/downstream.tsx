import type React from 'react'
import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import type { DownstreamPricingRow, DownstreamPricingUpsertBody } from '@/api/gateway'
import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { DownstreamPricingFormDialog } from '@/features/gateway-pricing/downstream-pricing-form-dialog'
import { formatRateLine } from '@/features/gateway-pricing/format'
import { PricingTable, type PricingTableColumn } from '@/features/gateway-pricing/pricing-table'
import { Pencil, RefreshCw, RotateCcw } from '@/lib/lucide-icons'
import { useUserPreferenceStore } from '@/stores/user-preference'

const columns: readonly PricingTableColumn[] = [
  { key: 'model', label: '模型 ID', className: 'px-3 py-2' },
  { key: 'strategy', label: '策略', className: 'px-3 py-2' },
  { key: 'rate', label: '生效价', className: 'px-3 py-2' },
  { key: 'version', label: '版本', className: 'px-3 py-2' },
  { key: 'actions', label: '操作', className: 'px-3 py-2 text-right' },
]

export default function GatewayPricingDownstreamPage(): React.JSX.Element {
  const currency = useUserPreferenceStore((s) => s.displayCurrency)
  const qc = useQueryClient()
  const [editingRow, setEditingRow] = useState<DownstreamPricingRow | null>(null)
  const [formOpen, setFormOpen] = useState(false)

  const downstreamQuery = useQuery({
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

  const upsertMut = useMutation({
    mutationFn: (body: DownstreamPricingUpsertBody) => gatewayApi.createDownstreamPricing(body),
    onSuccess: () => {
      toast.success('下游售价已保存为新版本')
      setFormOpen(false)
      setEditingRow(null)
      void qc.invalidateQueries({ queryKey: ['gateway-pricing-downstream'] })
      void qc.invalidateQueries({ queryKey: ['gateway-pricing-my'] })
    },
    onError: () => {
      toast.error('保存失败，请检查价格配置')
    },
  })

  const restoreMirror = (row: DownstreamPricingRow): void => {
    if (!row.gateway_model_id) return
    upsertMut.mutate({
      scope: 'team',
      gateway_model_id: row.gateway_model_id,
      inheritance_strategy: 'mirror',
      currency,
      amount_per_million: null,
    })
  }

  const rows = downstreamQuery.data ?? []

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
          <RefreshCw
            className={syncMut.isPending ? 'mr-1.5 h-4 w-4 animate-spin' : 'mr-1.5 h-4 w-4'}
          />
          一键同步上游
        </Button>
        <span className="text-xs text-muted-foreground">为尚未覆盖的模型创建「跟随上游」售价</span>
      </div>

      <PricingTable
        columns={columns}
        loading={downstreamQuery.isLoading}
        error={downstreamQuery.isError}
        empty={rows.length === 0}
        onRetry={() => {
          void downstreamQuery.refetch()
        }}
      >
        {rows.map((row) => (
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
            <td className="px-3 py-2 text-muted-foreground">v{row.version}</td>
            <td className="px-3 py-2 text-right">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditingRow(row)
                  setFormOpen(true)
                }}
              >
                <Pencil className="mr-1.5 h-4 w-4" aria-hidden="true" />
                调价
              </Button>
              {row.inheritance_strategy !== 'mirror' && row.gateway_model_id ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={upsertMut.isPending}
                  onClick={() => {
                    restoreMirror(row)
                  }}
                >
                  <RotateCcw className="mr-1.5 h-4 w-4" aria-hidden="true" />
                  跟随上游
                </Button>
              ) : null}
            </td>
          </tr>
        ))}
      </PricingTable>

      <DownstreamPricingFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        row={editingRow}
        currency={currency}
        submitting={upsertMut.isPending}
        onSubmit={(body) => {
          upsertMut.mutate(body)
        }}
      />
    </div>
  )
}
