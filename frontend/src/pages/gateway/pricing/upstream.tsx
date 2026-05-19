import type React from 'react'
import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { formatRateLine } from '@/features/gateway-pricing/format'
import { RefreshCw, ShieldAlert } from '@/lib/lucide-icons'
import { useUserPreferenceStore } from '@/stores/user-preference'

export default function GatewayPricingUpstreamPage(): React.JSX.Element {
  const currency = useUserPreferenceStore((s) => s.displayCurrency)
  const queryClient = useQueryClient()
  const [auditOpen, setAuditOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['gateway-pricing-upstream', currency],
    queryFn: () => gatewayApi.listUpstreamPricing({ currency }),
  })

  const auditQuery = useQuery({
    queryKey: ['gateway-pricing-upstream-audit'],
    queryFn: () => gatewayApi.auditUpstreamPricing(),
    enabled: auditOpen,
  })

  const syncMutation = useMutation({
    mutationFn: () => gatewayApi.syncUpstreamFromLitellm(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['gateway-pricing-upstream'] })
      setAuditOpen(true)
      await queryClient.invalidateQueries({ queryKey: ['gateway-pricing-upstream-audit'] })
    },
  })

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">加载中…</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={syncMutation.isPending}
          onClick={() => {
            syncMutation.mutate()
          }}
        >
          <RefreshCw
            className={syncMutation.isPending ? 'mr-1.5 h-4 w-4 animate-spin' : 'mr-1.5 h-4 w-4'}
            aria-hidden="true"
          />
          从 LiteLLM 同步价表
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setAuditOpen(true)
          }}
        >
          <ShieldAlert className="mr-1.5 h-4 w-4" aria-hidden="true" />
          键名诊断
        </Button>
        {syncMutation.isSuccess ? (
          <span className="text-xs text-muted-foreground">
            同步：新增 {syncMutation.data.created}，更新 {syncMutation.data.updated}，跳过 manual{' '}
            {syncMutation.data.skipped_manual}
          </span>
        ) : null}
        {syncMutation.isError ? (
          <span className="text-xs text-destructive">同步失败，请稍后重试</span>
        ) : null}
      </div>

      {auditOpen && auditQuery.data ? (
        <div className="rounded-md border border-amber-500/30 bg-amber-50/50 p-3 text-xs dark:bg-amber-950/20">
          <p className="font-medium text-amber-800 dark:text-amber-200">上游价目键诊断</p>
          <p className="mt-1 text-muted-foreground">
            已注册上游键 {auditQuery.data.registered_upstream_keys} 条
          </p>
          {auditQuery.data.models_without_upstream.length > 0 ? (
            <div className="mt-2">
              <p className="text-amber-800 dark:text-amber-200">
                有模型无上游价（{auditQuery.data.models_without_upstream.length}）：
              </p>
              <ul className="mt-1 list-inside list-disc font-mono">
                {auditQuery.data.models_without_upstream.slice(0, 8).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {auditQuery.data.upstream_without_model.length > 0 ? (
            <div className="mt-2">
              <p className="text-muted-foreground">
                孤立上游价（{auditQuery.data.upstream_without_model.length}）：
              </p>
              <ul className="mt-1 list-inside list-disc font-mono">
                {auditQuery.data.upstream_without_model.slice(0, 8).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-left text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Provider</th>
              <th className="px-3 py-2">上游模型</th>
              <th className="px-3 py-2">能力</th>
              <th className="px-3 py-2">单价 / 1M</th>
              <th className="px-3 py-2">来源</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((row) => (
              <tr key={row.id} className="cv-auto-row border-t">
                <td className="px-3 py-2">{row.provider}</td>
                <td className="px-3 py-2 font-mono text-xs">{row.upstream_model}</td>
                <td className="px-3 py-2">{row.capability}</td>
                <td className="px-3 py-2 tabular-nums">
                  {formatRateLine(
                    row.input_cost_per_million_display,
                    row.output_cost_per_million_display,
                    currency
                  )}
                </td>
                <td className="px-3 py-2 text-muted-foreground">{row.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
