import type React from 'react'
import { useCallback, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { modelsApi } from '@/api/gateway/models'
import type {
  EffectiveProvider,
  UpstreamPricingRow,
  UpstreamPricingUpsertBody,
} from '@/api/gateway/pricing'
import { pricingApi } from '@/api/gateway/pricing'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { PricingTable, type PricingTableColumn } from '@/features/gateway-pricing/pricing-table'
import { UpstreamMissingModelsBanner } from '@/features/gateway-pricing/upstream-missing-models-banner'
import { UpstreamPricingFormDialog } from '@/features/gateway-pricing/upstream-pricing-form-dialog'
import { UpstreamPricingTableRow } from '@/features/gateway-pricing/upstream-pricing-table-row'
import {
  buildLinkedModelKeys,
  buildUpstreamPricingKeySet,
  filterUpstreamRows,
  findModelsMissingUpstream,
  UPSTREAM_DISPLAY_CURRENCY,
} from '@/features/gateway-pricing/upstream-pricing-view'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Loader2, Plus, RefreshCw } from '@/lib/lucide-icons'

const columns: readonly PricingTableColumn[] = [
  { key: 'provider', label: '提供商', className: 'px-3 py-2' },
  { key: 'model', label: '上游模型', className: 'px-3 py-2' },
  { key: 'rate', label: '单价（USD / 1M）', className: 'px-3 py-2' },
  { key: 'source', label: '来源', className: 'px-3 py-2' },
  { key: 'actions', label: '操作', className: 'px-3 py-2 text-right' },
]

const EMPTY_EFFECTIVE_PROVIDERS: readonly EffectiveProvider[] = []

const UPSTREAM_PAGE_QUERY_KEYS = {
  upstream: ['gateway-pricing-upstream', UPSTREAM_DISPLAY_CURRENCY] as const,
  providers: ['gateway-pricing-effective-providers'] as const,
  models: ['gateway-models-for-upstream-pricing'] as const,
}

function toProviderSet(ids: readonly string[]): Set<string> {
  return new Set(ids)
}

export default function GatewayPricingUpstreamPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const queryClient = useQueryClient()
  const [syncOpen, setSyncOpen] = useState(false)
  const [selectedSyncProviders, setSelectedSyncProviders] = useState<string[]>([])
  const [selectedFilterProviders, setSelectedFilterProviders] = useState<string[]>([])
  const [onlyLinkedModels, setOnlyLinkedModels] = useState(true)
  const [editingRow, setEditingRow] = useState<UpstreamPricingRow | null>(null)
  const [formOpen, setFormOpen] = useState(false)

  const upstreamQuery = useQuery({
    queryKey: [...UPSTREAM_PAGE_QUERY_KEYS.upstream, teamId],
    queryFn: () => pricingApi.listUpstreamPricing(teamId, { currency: UPSTREAM_DISPLAY_CURRENCY }),
  })

  const providersQuery = useQuery({
    queryKey: [...UPSTREAM_PAGE_QUERY_KEYS.providers, teamId],
    queryFn: () => pricingApi.getEffectiveProviders(teamId),
  })

  const modelsQuery = useQuery({
    queryKey: [...UPSTREAM_PAGE_QUERY_KEYS.models, teamId],
    queryFn: () => modelsApi.listModels(teamId, { registry_scope: 'callable' }),
  })

  const effectiveProviders = providersQuery.data ?? EMPTY_EFFECTIVE_PROVIDERS
  const effectiveProviderSet = useMemo(
    () => new Set(effectiveProviders.map((p) => p.provider)),
    [effectiveProviders]
  )
  const selectedFilterProviderSet = useMemo(
    () => toProviderSet(selectedFilterProviders),
    [selectedFilterProviders]
  )
  const selectedSyncProviderSet = useMemo(
    () => toProviderSet(selectedSyncProviders),
    [selectedSyncProviders]
  )

  const models = modelsQuery.data
  const upstreamRows = upstreamQuery.data

  const linkedKeys = useMemo(() => buildLinkedModelKeys(models ?? []), [models])

  const upstreamKeys = useMemo(() => buildUpstreamPricingKeySet(upstreamRows ?? []), [upstreamRows])

  const visibleRows = useMemo(
    () =>
      filterUpstreamRows(upstreamRows ?? [], {
        effectiveProviders: effectiveProviderSet,
        linkedKeys,
        onlyLinkedModels,
        selectedProviders: selectedFilterProviderSet,
      }),
    [upstreamRows, effectiveProviderSet, linkedKeys, onlyLinkedModels, selectedFilterProviderSet]
  )

  const modelsMissingUpstream = useMemo(
    () => findModelsMissingUpstream(models ?? [], upstreamKeys),
    [models, upstreamKeys]
  )

  const syncMutation = useMutation({
    mutationFn: (providers: string[]) => pricingApi.syncUpstreamFromLitellm(teamId, { providers }),
    onSuccess: async (report) => {
      await queryClient.invalidateQueries({ queryKey: UPSTREAM_PAGE_QUERY_KEYS.upstream })
      setSyncOpen(false)
      toast.success(
        `已同步：新增 ${String(report.created)}，更新 ${String(report.updated)}，跳过手动覆盖 ${String(report.skipped_manual)} 条`
      )
    },
    onError: () => {
      toast.error('同步失败，请稍后重试')
    },
  })

  const upsertMutation = useMutation({
    mutationFn: (body: UpstreamPricingUpsertBody) => pricingApi.createUpstreamPricing(teamId, body),
    onSuccess: async () => {
      toast.success('上游成本已保存为新版本')
      setFormOpen(false)
      setEditingRow(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: UPSTREAM_PAGE_QUERY_KEYS.upstream }),
        queryClient.invalidateQueries({ queryKey: ['gateway-pricing-my'] }),
      ])
    },
    onError: () => {
      toast.error('保存上游成本失败，请检查价格配置')
    },
  })

  const toggleProvider = useCallback((provider: string, target: 'filter' | 'sync'): void => {
    const setter = target === 'filter' ? setSelectedFilterProviders : setSelectedSyncProviders
    setter((current) =>
      current.includes(provider)
        ? current.filter((item) => item !== provider)
        : [...current, provider]
    )
  }, [])

  const handleEditRow = useCallback((row: UpstreamPricingRow): void => {
    setEditingRow(row)
    setFormOpen(true)
  }, [])

  const handleOpenCreate = useCallback((): void => {
    setEditingRow(null)
    setFormOpen(true)
  }, [])

  const handleOpenSync = useCallback((): void => {
    setSelectedSyncProviders([...effectiveProviderSet])
    setSyncOpen(true)
  }, [effectiveProviderSet])

  const handleRetry = useCallback((): void => {
    void Promise.all([upstreamQuery.refetch(), providersQuery.refetch(), modelsQuery.refetch()])
  }, [upstreamQuery, providersQuery, modelsQuery])

  const tableLoading = upstreamQuery.isLoading || providersQuery.isLoading || modelsQuery.isLoading
  const tableError = upstreamQuery.isError || providersQuery.isError || modelsQuery.isError
  const showMissingBanner = modelsMissingUpstream.length > 0

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">
          上游成本对应各模型按 token 计费的输入 / 输出 token 单价，用于结算成本。前往
          <Link
            to="/gateway/models"
            className="mx-1 text-primary underline-offset-2 hover:underline"
          >
            模型
          </Link>
          页注册新模型；缺少上游成本时可一键从 LiteLLM 价表同步默认价。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          disabled={effectiveProviders.length === 0}
          onClick={handleOpenCreate}
        >
          <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
          新增价格
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={syncMutation.isPending || effectiveProviders.length === 0}
          onClick={handleOpenSync}
        >
          <RefreshCw
            className={syncMutation.isPending ? 'mr-1.5 h-4 w-4 animate-spin' : 'mr-1.5 h-4 w-4'}
            aria-hidden="true"
          />
          从 LiteLLM 同步
        </Button>
        {visibleRows.length > 0 ? (
          <span className="text-xs text-muted-foreground">共 {visibleRows.length} 条</span>
        ) : null}
      </div>

      {showMissingBanner ? <UpstreamMissingModelsBanner items={modelsMissingUpstream} /> : null}

      <div className="rounded-md border bg-card p-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">按提供商过滤</span>
          {effectiveProviders.length === 0 ? (
            <span className="text-xs text-muted-foreground">暂无已配置凭据的提供商</span>
          ) : (
            effectiveProviders.map((provider) => (
              <label key={provider.provider} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={selectedFilterProviderSet.has(provider.provider)}
                  onCheckedChange={() => {
                    toggleProvider(provider.provider, 'filter')
                  }}
                />
                <span>
                  {providerLabel(provider.provider)}
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({provider.credential_count})
                  </span>
                </span>
              </label>
            ))
          )}
          {selectedFilterProviderSet.size > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelectedFilterProviders([])
              }}
            >
              清除筛选
            </Button>
          ) : null}
          <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox
              checked={onlyLinkedModels}
              onCheckedChange={(checked) => {
                setOnlyLinkedModels(checked === true)
              }}
            />
            仅显示已绑定模型
          </label>
        </div>
      </div>

      <PricingTable
        columns={columns}
        loading={tableLoading}
        error={tableError}
        empty={visibleRows.length === 0}
        onRetry={handleRetry}
      >
        {visibleRows.map((row) => (
          <UpstreamPricingTableRow key={row.id} row={row} onEdit={handleEditRow} />
        ))}
      </PricingTable>

      {visibleRows.length === 0 && !tableLoading && !tableError ? (
        <p className="text-center text-xs text-muted-foreground">
          {onlyLinkedModels
            ? '当前条件下没有匹配的上游成本，请取消勾选「仅显示已绑定模型」或从 LiteLLM 同步默认价，并检查已注册模型的 real_model 是否与上游键一致。'
            : '当前条件下没有匹配的上游成本。'}
        </p>
      ) : null}

      {syncOpen ? (
        <Dialog open={syncOpen} onOpenChange={setSyncOpen}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>从 LiteLLM 同步默认价格</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <p className="text-sm text-muted-foreground">
                选择要同步的提供商；仅会处理当前已配置凭据的提供商，已手动维护的价格不会被覆盖。
              </p>
              <div className="grid gap-2">
                {effectiveProviders.map((provider) => (
                  <Label key={provider.provider} className="flex items-center gap-2">
                    <Checkbox
                      checked={selectedSyncProviderSet.has(provider.provider)}
                      onCheckedChange={() => {
                        toggleProvider(provider.provider, 'sync')
                      }}
                    />
                    <span>
                      {providerLabel(provider.provider)}
                      <span className="ml-1 text-xs text-muted-foreground">
                        {provider.has_managed ? '平台' : ''}
                        {provider.has_managed && provider.has_user ? ' / ' : ''}
                        {provider.has_user ? '个人' : ''}
                      </span>
                    </span>
                  </Label>
                ))}
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setSyncOpen(false)
                }}
              >
                取消
              </Button>
              <Button
                type="button"
                disabled={syncMutation.isPending || selectedSyncProviderSet.size === 0}
                onClick={() => {
                  syncMutation.mutate(selectedSyncProviders)
                }}
              >
                {syncMutation.isPending ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : null}
                开始同步
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}

      {formOpen ? (
        <UpstreamPricingFormDialog
          open={formOpen}
          onOpenChange={setFormOpen}
          row={editingRow}
          providers={effectiveProviders}
          submitting={upsertMutation.isPending}
          onSubmit={(body) => {
            upsertMutation.mutate(body)
          }}
        />
      ) : null}
    </div>
  )
}
