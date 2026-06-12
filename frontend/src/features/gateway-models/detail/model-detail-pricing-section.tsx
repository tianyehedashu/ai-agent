import { useEffect, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { DownstreamPricingRow, UpstreamPricingRow } from '@/api/gateway'
import type { GatewayModel } from '@/api/gateway/models'
import { pricingApi } from '@/api/gateway/pricing'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ModelInspectorScope } from '@/features/gateway-models/detail/model-inspector'
import { useModelDetailPricingMutations } from '@/features/gateway-models/detail/use-model-detail-pricing-mutations'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { formatRateLine } from '@/features/gateway-pricing/format'
import {
  buildDownstreamPricingPayload,
  buildUpstreamPricingPayload,
  type DownstreamPricingFormValues,
  type UpstreamPricingFormValues,
} from '@/features/gateway-pricing/pricing-form-payloads'
import {
  UPSTREAM_DISPLAY_CURRENCY,
  upstreamPricingKey,
} from '@/features/gateway-pricing/upstream-pricing-view'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { Loader2, Pencil, RotateCcw, X } from '@/lib/lucide-icons'

interface ModelDetailPricingSectionProps {
  model: GatewayModel
  scope: ModelInspectorScope
  teamId: string
}

type EditingTarget = 'downstream' | 'upstream' | null

function downstreamInitial(
  row: DownstreamPricingRow | null,
  modelId: string
): DownstreamPricingFormValues {
  return {
    gateway_model_id: row?.gateway_model_id ?? modelId,
    inheritance_strategy: row?.inheritance_strategy === 'mirror' ? 'mirror' : 'manual',
    input: row?.input_cost_per_million_display?.amount ?? '',
    output: row?.output_cost_per_million_display?.amount ?? '',
    cache_creation: '',
    cache_read: '',
    per_request: '',
  }
}

function upstreamInitial(
  row: UpstreamPricingRow | null,
  model: GatewayModel
): UpstreamPricingFormValues {
  return {
    provider: row?.provider ?? model.provider,
    upstream_model: row?.upstream_model ?? model.real_model,
    capability: row?.capability ?? (model.capability || 'chat'),
    input: row?.input_cost_per_million_display?.amount ?? '',
    output: row?.output_cost_per_million_display?.amount ?? '',
    cache_creation: '',
    cache_read: '',
  }
}

function PricingRow({
  label,
  value,
  badge,
  loading,
  actions,
  inlineForm,
}: {
  label: string
  value: React.ReactNode
  badge?: string | null
  loading?: boolean
  actions?: React.ReactNode
  inlineForm?: React.ReactNode
}): React.JSX.Element {
  return (
    <div className="border-b border-border/50 py-2 last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">{label}</span>
            {badge ? (
              <Badge variant="secondary" className="text-[10px] font-normal">
                {badge}
              </Badge>
            ) : null}
          </div>
          {loading ? (
            <div className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              加载…
            </div>
          ) : (
            <div className="mt-0.5 text-sm tabular-nums">{value}</div>
          )}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-1.5">{actions}</div> : null}
      </div>
      {inlineForm ? <div className="mt-2">{inlineForm}</div> : null}
    </div>
  )
}

export function ModelDetailPricingSection({
  model,
  scope,
  teamId,
}: ModelDetailPricingSectionProps): React.JSX.Element {
  const { isAdmin, isPlatformAdmin } = useGatewayPermission()
  const currency = GATEWAY_DISPLAY_CURRENCY
  const isTeamScope = scope === 'team'
  const showDownstreamEdit = isTeamScope && isAdmin
  const showUpstreamEdit = isPlatformAdmin

  const [editing, setEditing] = useState<EditingTarget>(null)
  const [downstreamValues, setDownstreamValues] = useState<DownstreamPricingFormValues>(() =>
    downstreamInitial(null, model.id)
  )
  const [upstreamValues, setUpstreamValues] = useState<UpstreamPricingFormValues>(() =>
    upstreamInitial(null, model)
  )

  const { byName: priceByName } = useGatewayModelPrices(currency)
  const myPrice = priceByName.get(model.name)

  const downstreamQuery = useQuery({
    queryKey: ['gateway-pricing-downstream', teamId, currency],
    queryFn: () => gatewayApi.listDownstreamPricing(teamId, { scope: 'tenant', currency }),
    enabled: isTeamScope && teamId.length > 0,
  })

  const upstreamQuery = useQuery({
    queryKey: ['gateway-pricing-upstream', UPSTREAM_DISPLAY_CURRENCY, teamId],
    queryFn: () => pricingApi.listUpstreamPricing(teamId, { currency: UPSTREAM_DISPLAY_CURRENCY }),
    enabled: teamId.length > 0,
  })

  const downstreamRow = useMemo(() => {
    if (!isTeamScope) return null
    return (downstreamQuery.data ?? []).find((row) => row.gateway_model_id === model.id) ?? null
  }, [downstreamQuery.data, isTeamScope, model.id])

  const upstreamRow = useMemo(() => {
    const key = upstreamPricingKey(model.provider, model.real_model, model.capability || 'chat')
    return (
      (upstreamQuery.data ?? []).find(
        (row) => upstreamPricingKey(row.provider, row.upstream_model, row.capability) === key
      ) ?? null
    )
  }, [model.capability, model.provider, model.real_model, upstreamQuery.data])

  const {
    upsertDownstream,
    restoreDownstreamMirror,
    upsertUpstream,
    downstreamPending,
    upstreamPending,
  } = useModelDetailPricingMutations({
    teamId,
    onDownstreamSuccess: () => {
      setEditing(null)
    },
    onUpstreamSuccess: () => {
      setEditing(null)
    },
  })

  useEffect(() => {
    if (editing === 'downstream') {
      setDownstreamValues(downstreamInitial(downstreamRow, model.id))
    }
  }, [editing, downstreamRow, model.id])

  useEffect(() => {
    if (editing === 'upstream') {
      setUpstreamValues(upstreamInitial(upstreamRow, model))
    }
  }, [editing, upstreamRow, model])

  const myPriceLine = myPrice
    ? formatRateLine(
        myPrice.input_cost_per_million_display,
        myPrice.output_cost_per_million_display,
        currency
      )
    : '—'

  const downstreamLine = downstreamRow
    ? formatRateLine(
        downstreamRow.input_cost_per_million_display,
        downstreamRow.output_cost_per_million_display,
        currency
      )
    : '未配置'

  const upstreamLine = upstreamRow
    ? formatRateLine(
        upstreamRow.input_cost_per_million_display,
        upstreamRow.output_cost_per_million_display,
        UPSTREAM_DISPLAY_CURRENCY
      )
    : '未登记'

  const downstreamManual = downstreamValues.inheritance_strategy === 'manual'
  const canSubmitDownstream =
    !downstreamPending &&
    (!downstreamManual ||
      (Number.isFinite(Number(downstreamValues.input)) &&
        Number.isFinite(Number(downstreamValues.output))))

  const canSubmitUpstream =
    !upstreamPending &&
    Boolean(upstreamValues.upstream_model.trim()) &&
    Number.isFinite(Number(upstreamValues.input)) &&
    Number.isFinite(Number(upstreamValues.output))

  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">定价</h3>

      <div className="rounded-md border border-border/60 bg-muted/10 px-3 py-1">
        <PricingRow
          label="生效售价"
          value={myPriceLine}
          badge={
            myPrice?.inheritance_strategy === 'mirror'
              ? '跟随上游'
              : myPrice?.inheritance_strategy === 'manual'
                ? '自定义'
                : null
          }
        />

        {isTeamScope ? (
          <PricingRow
            label="下游售价"
            loading={downstreamQuery.isLoading}
            value={downstreamLine}
            badge={
              downstreamRow?.inheritance_strategy === 'mirror'
                ? '跟随上游'
                : downstreamRow?.inheritance_strategy === 'manual'
                  ? '自定义'
                  : null
            }
            actions={
              showDownstreamEdit && editing !== 'downstream' ? (
                <>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    disabled={downstreamPending}
                    onClick={() => {
                      setEditing('downstream')
                    }}
                  >
                    <Pencil className="mr-1 h-3 w-3" />
                    调价
                  </Button>
                  {downstreamRow && downstreamRow.inheritance_strategy !== 'mirror' ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      disabled={downstreamPending}
                      onClick={() => {
                        restoreDownstreamMirror(model.id)
                      }}
                    >
                      {downstreamPending ? (
                        <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                      ) : (
                        <RotateCcw className="mr-1 h-3 w-3" />
                      )}
                      跟随上游
                    </Button>
                  ) : null}
                </>
              ) : undefined
            }
            inlineForm={
              editing === 'downstream' ? (
                <div className="space-y-3 rounded-md border border-primary/20 bg-background p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">调整下游售价</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => {
                        setEditing(null)
                      }}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <Select
                    value={downstreamValues.inheritance_strategy}
                    onValueChange={(v) => {
                      setDownstreamValues((c) => ({
                        ...c,
                        inheritance_strategy: v as 'mirror' | 'manual',
                      }))
                    }}
                  >
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="mirror">跟随上游</SelectItem>
                      <SelectItem value="manual">自定义售价</SelectItem>
                    </SelectContent>
                  </Select>
                  {downstreamManual ? (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="space-y-1">
                        <Label className="text-xs">输入 / 1M ({currency})</Label>
                        <Input
                          className="h-8"
                          type="number"
                          min="0"
                          step="0.0001"
                          value={downstreamValues.input}
                          onChange={(e) => {
                            setDownstreamValues((c) => ({ ...c, input: e.target.value }))
                          }}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">输出 / 1M ({currency})</Label>
                        <Input
                          className="h-8"
                          type="number"
                          min="0"
                          step="0.0001"
                          value={downstreamValues.output}
                          onChange={(e) => {
                            setDownstreamValues((c) => ({ ...c, output: e.target.value }))
                          }}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">保存后将跟随上游成本定价。</p>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => {
                        setEditing(null)
                      }}
                    >
                      取消
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="h-7 text-xs"
                      disabled={!canSubmitDownstream}
                      onClick={() => {
                        upsertDownstream(buildDownstreamPricingPayload(downstreamValues, currency))
                      }}
                    >
                      {downstreamPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
                      保存
                    </Button>
                  </div>
                </div>
              ) : undefined
            }
          />
        ) : null}

        <PricingRow
          label="上游成本"
          loading={upstreamQuery.isLoading}
          value={upstreamLine}
          actions={
            showUpstreamEdit && editing !== 'upstream' ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                disabled={upstreamPending}
                onClick={() => {
                  setEditing('upstream')
                }}
              >
                <Pencil className="mr-1 h-3 w-3" />
                {upstreamRow ? '调整' : '登记'}
              </Button>
            ) : undefined
          }
          inlineForm={
            editing === 'upstream' ? (
              <div className="space-y-3 rounded-md border border-primary/20 bg-background p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">上游成本 (USD)</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => {
                      setEditing(null)
                    }}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <p className="font-mono text-xs text-muted-foreground">
                  {model.provider}/{model.real_model}
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label className="text-xs">输入 / 1M</Label>
                    <Input
                      className="h-8"
                      type="number"
                      min="0"
                      step="0.0001"
                      value={upstreamValues.input}
                      onChange={(e) => {
                        setUpstreamValues((c) => ({ ...c, input: e.target.value }))
                      }}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">输出 / 1M</Label>
                    <Input
                      className="h-8"
                      type="number"
                      min="0"
                      step="0.0001"
                      value={upstreamValues.output}
                      onChange={(e) => {
                        setUpstreamValues((c) => ({ ...c, output: e.target.value }))
                      }}
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => {
                      setEditing(null)
                    }}
                  >
                    取消
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    className="h-7 text-xs"
                    disabled={!canSubmitUpstream}
                    onClick={() => {
                      upsertUpstream(
                        buildUpstreamPricingPayload(upstreamValues, UPSTREAM_DISPLAY_CURRENCY)
                      )
                    }}
                  >
                    {upstreamPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
                    保存
                  </Button>
                </div>
              </div>
            ) : undefined
          }
        />
      </div>
    </section>
  )
}
