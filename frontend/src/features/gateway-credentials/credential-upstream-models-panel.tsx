/**
 * 凭据上游模型探测：探测 / 刷新、不支持标记、多选后批量入库（与后端契约对齐）。
 */

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  type CredentialProbeResult,
  type PersonalModelBatchImportBody,
  type PersonalModelBatchImportResponse,
  type TeamGatewayModelBatchImportBody,
  type TeamGatewayModelBatchImportResponse,
  gatewayApi,
} from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  credentialProbeCacheKey,
  invalidateCredentialProbeCache,
  isProbeCacheFresh,
} from '@/features/gateway-credentials/credential-probe-cache'
import {
  type CredentialUpstreamScope,
  isPersonalUpstreamScope,
} from '@/features/gateway-credentials/types'
import {
  countProbeItems,
  isImportableUpstreamItem,
} from '@/features/gateway-credentials/upstream-import-utils'
import { UpstreamModelList } from '@/features/gateway-credentials/upstream-model-list'
import { CapabilityField } from '@/features/gateway-models/capability-field'
import { resolveUpstreamModelTypes } from '@/features/gateway-models/infer-model-types'
import { gatewayModelsByCredentialInvalidatePrefix } from '@/features/gateway-models/query-keys'
import {
  chunkBatchImportItems,
  type PersonalModelBatchImportItem,
} from '@/features/gateway-models/utils'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Loader2, RefreshCw, Search } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

export type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'

async function runChunkedPersonalImport(
  credentialId: string,
  base: Omit<PersonalModelBatchImportBody, 'items'>,
  items: PersonalModelBatchImportItem[]
): Promise<PersonalModelBatchImportResponse> {
  const chunks = chunkBatchImportItems(items)
  const merged: PersonalModelBatchImportResponse = {
    credential_id: credentialId,
    created: [],
    failed: [],
  }
  for (const chunk of chunks) {
    const res = await gatewayApi.batchImportMyModelsFromUpstream(credentialId, {
      ...base,
      items: chunk,
    })
    merged.created.push(...res.created)
    merged.failed.push(...res.failed)
  }
  return merged
}

async function runChunkedTeamImport(
  teamId: string,
  credentialId: string,
  base: Omit<TeamGatewayModelBatchImportBody, 'items'>,
  teamItems: TeamGatewayModelBatchImportBody['items']
): Promise<TeamGatewayModelBatchImportResponse> {
  const chunkSize = 50
  const merged: TeamGatewayModelBatchImportResponse = {
    credential_id: credentialId,
    created: [],
    failed: [],
  }
  for (let i = 0; i < teamItems.length; i += chunkSize) {
    const chunk = teamItems.slice(i, i + chunkSize)
    const res = await gatewayApi.batchImportTeamModelsFromUpstream(teamId, credentialId, {
      ...base,
      items: chunk,
    })
    merged.created.push(...res.created)
    merged.failed.push(...res.failed)
  }
  return merged
}

export interface CredentialUpstreamModelsPanelProps {
  scope: CredentialUpstreamScope
  credentialId: string
  provider: string
  disabled?: boolean
  onPickModelId?: (upstreamId: string) => void
  embedded?: boolean
  autoProbe?: boolean
  onImported?: (createdCount: number, modelIds?: string[]) => void
  cacheKey?: readonly unknown[]
  onProbeResult?: (result: CredentialProbeResult) => void
}

function supportBadge(support: CredentialProbeResult['support']): {
  label: string
  variant: 'default' | 'secondary' | 'destructive' | 'outline'
} {
  switch (support) {
    case 'full':
      return { label: '已列举', variant: 'default' }
    case 'unsupported':
      return { label: '不支持自动列举', variant: 'secondary' }
    case 'error':
      return { label: '探测失败', variant: 'destructive' }
    case 'partial':
      return { label: '部分列举', variant: 'outline' }
    default:
      return { label: support, variant: 'outline' }
  }
}

function formatProbeTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function readCachedProbe(
  queryClient: ReturnType<typeof useQueryClient>,
  cacheKey: readonly unknown[]
): CredentialProbeResult | null {
  return queryClient.getQueryData<CredentialProbeResult>(cacheKey) ?? null
}

function ProbeStatusAlert({ probe }: { probe: CredentialProbeResult }): React.JSX.Element {
  const isError = probe.support === 'error'
  const message =
    probe.message ?? (isError ? '上游列举失败' : '此提供商不支持自动列举模型，请改用手动注册。')
  return (
    <div
      role="status"
      className={cn(
        'rounded-md border px-3 py-2 text-sm',
        isError
          ? 'border-destructive/30 bg-destructive/5 text-destructive'
          : 'border-amber-500/30 bg-amber-500/5 text-amber-900 dark:text-amber-200'
      )}
    >
      <p>{message}</p>
      {probe.http_status !== null && probe.http_status !== undefined ? (
        <p className="mt-1 text-xs opacity-80">HTTP {String(probe.http_status)}</p>
      ) : null}
    </div>
  )
}

export function CredentialUpstreamModelsPanel({
  scope,
  credentialId,
  provider,
  disabled = false,
  onPickModelId,
  embedded = false,
  autoProbe = false,
  onImported,
  cacheKey: cacheKeyProp,
  onProbeResult,
}: CredentialUpstreamModelsPanelProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const cacheKey = cacheKeyProp ?? credentialProbeCacheKey(scope, credentialId)
  const manualProbeRef = useRef(false)

  const [probe, setProbe] = useState<CredentialProbeResult | null>(() =>
    readCachedProbe(queryClient, cacheKey)
  )
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')
  const deferredFilter = useDeferredValue(filter)
  const [displayNamePrefix, setDisplayNamePrefix] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [capability, setCapability] = useState('chat')
  const [hideRegistered, setHideRegistered] = useState(false)

  const writeProbeCache = useCallback(
    (data: CredentialProbeResult) => {
      queryClient.setQueryData(cacheKey, data)
    },
    [queryClient, cacheKey]
  )

  const applyProbeResult = useCallback(
    (data: CredentialProbeResult) => {
      setProbe(data)
      onProbeResult?.(data)
    },
    [onProbeResult]
  )

  const probeMutation = useMutation({
    mutationFn: async () =>
      isPersonalUpstreamScope(scope)
        ? gatewayApi.probeMyCredential(credentialId)
        : gatewayApi.probeTeamCredential(teamId, credentialId),
    onSuccess: (data) => {
      writeProbeCache(data)
      setSelected(new Set())
      applyProbeResult(data)
      if (manualProbeRef.current) {
        const stats =
          data.support === 'full' || data.support === 'partial' ? countProbeItems(data.items) : null
        toast({
          title: '探测完成',
          description:
            stats !== null
              ? `共 ${String(stats.total)} 个，可导入 ${String(stats.importable)} 个${
                  stats.registered > 0 ? `，已注册 ${String(stats.registered)} 个` : ''
                }`
              : (data.message ?? '上游不支持自动列举模型'),
        })
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '探测失败', description: e.message })
    },
    onSettled: () => {
      manualProbeRef.current = false
    },
  })

  // 单次 effect：凭据/缓存键变化时同步缓存；旧缓存先展示，缓存过期时后台刷新。
  useEffect(() => {
    const cached = readCachedProbe(queryClient, cacheKey)
    if (cached) applyProbeResult(cached)

    if (!autoProbe || disabled || credentialId.length === 0) return
    if (probeMutation.isPending) return
    if (isProbeCacheFresh(queryClient, cacheKey)) return
    probeMutation.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在打开/凭据变化时自动探测
  }, [autoProbe, disabled, credentialId, cacheKey, queryClient, applyProbeResult])

  const batchMutation = useMutation({
    mutationFn: async () => {
      const selectedRows = [...selected]
        .map((id) => probe?.items.find((it) => it.id === id))
        .filter((row): row is NonNullable<typeof row> => row !== undefined)
        .filter((row) => isImportableUpstreamItem(row, provider))
      if (selectedRows.length === 0) throw new Error('请至少选择一条可导入的上游模型')
      if (isPersonalUpstreamScope(scope)) {
        const importItems: PersonalModelBatchImportItem[] = selectedRows.map((row) => ({
          upstream_model_id: row.id,
          model_types: resolveUpstreamModelTypes(row, provider),
        }))
        const base = {
          provider,
          display_name_prefix: displayNamePrefix.trim() || null,
          enabled,
          tags: null,
        }
        return runChunkedPersonalImport(credentialId, base, importItems)
      }
      const teamItems = selectedRows.map((row) => ({
        upstream_model_id: row.id,
        name: null as string | null,
      }))
      const teamBase = {
        provider,
        capability,
        weight: 1,
        rpm_limit: null,
        tpm_limit: null,
        tags: null,
        enabled,
      }
      return runChunkedTeamImport(teamId, credentialId, teamBase, teamItems)
    },
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-models'] })
      void queryClient.invalidateQueries({
        queryKey: gatewayModelsByCredentialInvalidatePrefix(credentialId, teamId),
      })
      const dupFailed = res.failed.filter((f) => f.reason.includes('已注册'))
      toast({
        title: '导入完成',
        description: `成功 ${String(res.created.length)} 条，失败 ${String(res.failed.length)} 条${
          dupFailed.length > 0 ? `（含 ${String(dupFailed.length)} 条已注册）` : ''
        }`,
      })
      setSelected(new Set())
      invalidateCredentialProbeCache(queryClient, scope, credentialId)
      if (!disabled && credentialId.length > 0) {
        probeMutation.mutate()
      }
      if (res.created.length > 0) {
        const modelIds = isPersonalUpstreamScope(scope)
          ? res.created.flatMap((item) =>
              'gateway_model_ids' in item ? item.gateway_model_ids : []
            )
          : []
        const importedCount = modelIds.length > 0 ? modelIds.length : res.created.length
        onImported?.(importedCount, modelIds.length > 0 ? modelIds : undefined)
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '批量导入失败', description: e.message })
    },
  })

  const probeStats = useMemo(
    () => (probe?.items ? countProbeItems(probe.items, provider) : null),
    [probe?.items, provider]
  )

  const probeItemsById = useMemo(
    () => (probe?.items ? new Map(probe.items.map((it) => [it.id, it])) : null),
    [probe?.items]
  )

  const filterIsStale = filter !== deferredFilter
  const filteredItems = useMemo(() => {
    if (!probe?.items) return []
    let rows = probe.items
    if (hideRegistered) {
      rows = rows.filter((it) => isImportableUpstreamItem(it, provider))
    }
    const q = deferredFilter.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((it) => it.id.toLowerCase().includes(q))
  }, [probe, deferredFilter, hideRegistered, provider])

  const importableVisibleItems = useMemo(
    () => filteredItems.filter((it) => isImportableUpstreamItem(it, provider)),
    [filteredItems, provider]
  )

  const selectedImportableCount = useMemo(() => {
    if (!probeItemsById) return 0
    let count = 0
    for (const id of selected) {
      const row = probeItemsById.get(id)
      if (row !== undefined && isImportableUpstreamItem(row, provider)) count++
    }
    return count
  }, [probeItemsById, selected, provider])

  const visibleSelectedCount = importableVisibleItems.reduce(
    (count, item) => count + (selected.has(item.id) ? 1 : 0),
    0
  )
  const allVisibleSelected =
    importableVisibleItems.length > 0 && visibleSelectedCount === importableVisibleItems.length

  const toggle = useCallback(
    (id: string) => {
      const row = probeItemsById?.get(id)
      if (row !== undefined && !isImportableUpstreamItem(row, provider)) return
      setSelected((prev) => {
        const next = new Set(prev)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        return next
      })
    },
    [probeItemsById, provider]
  )

  const toggleAllVisible = useCallback(() => {
    const ids = importableVisibleItems.map((i) => i.id)
    if (ids.length === 0) return
    setSelected((prev) => {
      const next = new Set(prev)
      if (allVisibleSelected) ids.forEach((id) => next.delete(id))
      else ids.forEach((id) => next.add(id))
      return next
    })
  }, [allVisibleSelected, importableVisibleItems])

  const clearSelected = useCallback(() => {
    setSelected(new Set())
  }, [])

  const runProbe = useCallback(() => {
    manualProbeRef.current = true
    probeMutation.mutate()
  }, [probeMutation])

  const badge = probe ? supportBadge(probe.support) : null
  const canListProbeItems = probe?.support === 'full' || probe?.support === 'partial'

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2">
      {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
      {probe ? (
        <span className="text-xs text-muted-foreground">
          最近探测 {formatProbeTime(probe.probe_at)}
        </span>
      ) : null}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || probeMutation.isPending}
        onClick={runProbe}
      >
        {probeMutation.isPending ? (
          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <Search className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
        )}
        探测
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={disabled || probeMutation.isPending || !probe}
        onClick={runProbe}
        title="重新探测上游"
        aria-label="重新探测上游"
      >
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
      </Button>
    </div>
  )

  const statusBlock =
    probe && (probe.support === 'unsupported' || probe.support === 'error') ? (
      <ProbeStatusAlert probe={probe} />
    ) : probe?.message && canListProbeItems ? (
      <p className="text-sm text-muted-foreground">{probe.message}</p>
    ) : null

  const listBlock =
    canListProbeItems && probe.items.length > 0 ? (
      <>
        {probeStats !== null && probeStats.registered > 0 ? (
          <div
            role="status"
            className="rounded-md border border-muted bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
          >
            本凭据已有 {probeStats.registered}{' '}
            个模型注册过；列表中带「已注册」标记的行无法再次导入。
          </div>
        ) : null}
        <label className="flex w-fit cursor-pointer items-center gap-2 text-sm">
          <Checkbox
            id="hide-registered"
            checked={hideRegistered}
            onCheckedChange={(c) => {
              setHideRegistered(c === true)
            }}
          />
          <span>隐藏已注册</span>
        </label>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid flex-1 gap-1.5">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="upstream-filter">筛选模型 ID</Label>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                显示 {filteredItems.length}/{probe.items.length} · 可导入{' '}
                {probeStats?.importable ?? 0} · 已选 {selectedImportableCount} 个
              </span>
            </div>
            <Input
              id="upstream-filter"
              name="upstream-model-filter"
              autoComplete="off"
              spellCheck={false}
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value)
              }}
              placeholder="输入模型 ID，如 gpt-4…"
            />
          </div>
          <div className="flex shrink-0 items-end">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={selected.size === 0}
              onClick={clearSelected}
            >
              清空选择
            </Button>
          </div>
        </div>
        <UpstreamModelList
          items={filteredItems}
          provider={provider}
          selected={selected}
          onToggle={toggle}
          onPickModelId={onPickModelId}
          isStale={filterIsStale}
          importableCount={importableVisibleItems.length}
          allImportableSelected={allVisibleSelected}
          someImportableSelected={
            visibleSelectedCount > 0 && visibleSelectedCount < importableVisibleItems.length
          }
          onToggleAllImportable={toggleAllVisible}
        />
        <div className="flex flex-wrap items-end gap-3 border-t pt-4">
          {scope === 'user' ? (
            <div className="grid min-w-[12rem] flex-1 gap-1.5">
              <Label htmlFor="disp-prefix">显示名前缀（可选）</Label>
              <Input
                id="disp-prefix"
                value={displayNamePrefix}
                onChange={(e) => {
                  setDisplayNamePrefix(e.target.value)
                }}
                placeholder="留空则使用上游模型 id"
              />
            </div>
          ) : (
            <div className="min-w-[12rem] flex-1">
              <CapabilityField
                id="team-cap"
                value={capability}
                onValueChange={setCapability}
                showHint
              />
            </div>
          )}
          <div className="flex items-center gap-2 pb-0.5">
            <Switch
              id="import-enabled"
              checked={enabled}
              onCheckedChange={(c) => {
                setEnabled(c)
              }}
            />
            <Label htmlFor="import-enabled" className="cursor-pointer text-sm font-normal">
              导入后启用
            </Label>
          </div>
          <p className="w-full text-xs text-muted-foreground">
            类型按模型 ID 自动推断；多类型模型会创建多条个人记录。
          </p>
        </div>
        <div className="flex justify-end">
          <Button
            type="button"
            disabled={disabled || batchMutation.isPending || selectedImportableCount === 0}
            onClick={() => {
              batchMutation.mutate()
            }}
          >
            {batchMutation.isPending ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : null}
            导入选中项（{selectedImportableCount}）
          </Button>
        </div>
      </>
    ) : canListProbeItems && probe.items.length === 0 ? (
      <p className="text-sm text-muted-foreground" role="status">
        上游未返回任何模型。
      </p>
    ) : !probe && !probeMutation.isPending ? (
      <p className="text-sm text-muted-foreground">点击「探测」列举上游可用模型。</p>
    ) : null

  const pendingBlock = probeMutation.isPending ? (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {probe ? '正在重新探测上游…' : '正在探测上游…'}
    </div>
  ) : null

  const content = (
    <div className="space-y-4">
      {embedded ? (
        <div className="flex flex-wrap items-start justify-between gap-2 border-b pb-3">
          <div>
            <p className="text-sm font-medium">上游模型</p>
            <p className="text-xs text-muted-foreground">
              通过 OpenAI 兼容 <span className="font-mono">/api/v1/openai/v1/models</span> 列举
            </p>
          </div>
          {toolbar}
        </div>
      ) : null}
      {statusBlock}
      {pendingBlock}
      {listBlock}
    </div>
  )

  if (embedded) return content

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">上游模型探测</CardTitle>
            <CardDescription>
              通过 OpenAI 兼容 <span className="font-mono">/api/v1/openai/v1/models</span>{' '}
              列举可用模型；刷新即重新探测。
            </CardDescription>
          </div>
          {toolbar}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {statusBlock}
        {pendingBlock}
        {listBlock}
      </CardContent>
    </Card>
  )
}
