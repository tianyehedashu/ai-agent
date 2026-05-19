/**
 * 凭据上游模型探测：探测 / 刷新、不支持标记、多选后批量入库（与后端契约对齐）。
 */

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  type CredentialProbeResult,
  type PersonalModelBatchImportBody,
  type TeamGatewayModelBatchImportBody,
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
import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'
import {
  countProbeItems,
  isImportableUpstreamItem,
} from '@/features/gateway-credentials/upstream-import-utils'
import { UpstreamModelList } from '@/features/gateway-credentials/upstream-model-list'
import { CapabilityField } from '@/features/gateway-models/capability-field'
import { useToast } from '@/hooks/use-toast'
import { Loader2, RefreshCw, Search } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { ModelType } from '@/types/user-model'
import { MODEL_TYPE_LABELS } from '@/types/user-model'

export type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'

const IMPORT_MODEL_TYPES: ModelType[] = ['text', 'image', 'image_gen', 'video']

export interface CredentialUpstreamModelsPanelProps {
  scope: CredentialUpstreamScope
  credentialId: string
  provider: string
  disabled?: boolean
  onPickModelId?: (upstreamId: string) => void
  embedded?: boolean
  autoProbe?: boolean
  onImported?: (createdCount: number) => void
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
  const [modelTypes, setModelTypes] = useState<ModelType[]>(['text'])
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
      scope === 'user'
        ? gatewayApi.probeMyCredential(credentialId)
        : gatewayApi.probeTeamCredential(credentialId),
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
      const ids = [...selected].filter((id) => {
        const row = probe?.items.find((it) => it.id === id)
        return row !== undefined && isImportableUpstreamItem(row)
      })
      if (ids.length === 0) throw new Error('请至少选择一条可导入的上游模型')
      if (scope === 'user') {
        const body: PersonalModelBatchImportBody = {
          provider,
          upstream_model_ids: ids,
          model_types: modelTypes,
          display_name_prefix: displayNamePrefix.trim() || null,
          enabled,
          tags: null,
        }
        return gatewayApi.batchImportMyModelsFromUpstream(credentialId, body)
      }
      const body: TeamGatewayModelBatchImportBody = {
        provider,
        capability,
        weight: 1,
        rpm_limit: null,
        tpm_limit: null,
        tags: null,
        enabled,
        items: ids.map((upstream_model_id) => ({ upstream_model_id, name: null })),
      }
      return gatewayApi.batchImportTeamModelsFromUpstream(credentialId, body)
    },
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-models'] })
      void queryClient.invalidateQueries({
        queryKey: ['gateway', 'models', 'by-credential', credentialId],
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
      if (res.created.length > 0) onImported?.(res.created.length)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '批量导入失败', description: e.message })
    },
  })

  const probeStats = useMemo(
    () => (probe?.items ? countProbeItems(probe.items) : null),
    [probe?.items]
  )

  const filterIsStale = filter !== deferredFilter
  const filteredItems = useMemo(() => {
    if (!probe?.items) return []
    let rows = probe.items
    if (hideRegistered) {
      rows = rows.filter((it) => isImportableUpstreamItem(it))
    }
    const q = deferredFilter.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((it) => it.id.toLowerCase().includes(q))
  }, [probe, deferredFilter, hideRegistered])

  const importableVisibleItems = useMemo(
    () => filteredItems.filter((it) => isImportableUpstreamItem(it)),
    [filteredItems]
  )

  const selectedImportableCount = useMemo(() => {
    if (!probe?.items) return 0
    return [...selected].filter((id) => {
      const row = probe.items.find((it) => it.id === id)
      return row !== undefined && isImportableUpstreamItem(row)
    }).length
  }, [probe?.items, selected])

  const visibleSelectedCount = importableVisibleItems.reduce(
    (count, item) => count + (selected.has(item.id) ? 1 : 0),
    0
  )
  const allVisibleSelected =
    importableVisibleItems.length > 0 && visibleSelectedCount === importableVisibleItems.length

  const toggle = useCallback(
    (id: string) => {
      const row = probe?.items.find((it) => it.id === id)
      if (row !== undefined && !isImportableUpstreamItem(row)) return
      setSelected((prev) => {
        const next = new Set(prev)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        return next
      })
    },
    [probe?.items]
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

  function toggleModelType(t: ModelType): void {
    setModelTypes((cur) => {
      const next = cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]
      return next.length === 0 ? ['text'] : next
    })
  }

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
          <div className="flex shrink-0 gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={importableVisibleItems.length === 0}
              onClick={toggleAllVisible}
            >
              {allVisibleSelected
                ? '取消可见项'
                : `选择可导入项（${String(importableVisibleItems.length)}）`}
            </Button>
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
          selected={selected}
          onToggle={toggle}
          onPickModelId={onPickModelId}
          isStale={filterIsStale}
        />
        <div className="grid gap-4 border-t pt-4 sm:grid-cols-2">
          {scope === 'user' ? (
            <div className="grid gap-1.5">
              <Label htmlFor="disp-prefix">显示名前缀（可选）</Label>
              <Input
                id="disp-prefix"
                value={displayNamePrefix}
                onChange={(e) => {
                  setDisplayNamePrefix(e.target.value)
                }}
                placeholder="留空则使用上游模型 id 作为显示名"
              />
            </div>
          ) : (
            <CapabilityField
              id="team-cap"
              value={capability}
              onValueChange={setCapability}
              showHint
            />
          )}
          <div className="flex items-center gap-2">
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
        </div>
        {scope === 'user' ? (
          <div className="grid gap-1.5">
            <Label>导入为哪些模型类型</Label>
            <div className="flex flex-wrap gap-3">
              {IMPORT_MODEL_TYPES.map((t) => (
                <label key={t} className="flex cursor-pointer items-center gap-1.5 text-sm">
                  <Checkbox
                    checked={modelTypes.includes(t)}
                    onCheckedChange={() => {
                      toggleModelType(t)
                    }}
                  />
                  {MODEL_TYPE_LABELS[t]}
                </label>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              每选一种类型，会为同一个上游模型创建一条个人模型记录。
            </p>
          </div>
        ) : null}
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
              通过 OpenAI 兼容 <span className="font-mono">/v1/models</span> 列举
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
              通过 OpenAI 兼容 <span className="font-mono">/v1/models</span>{' '}
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
