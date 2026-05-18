/**
 * 凭据上游模型探测：探测 / 刷新、不支持标记、多选后批量入库（与后端契约对齐）。
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCw, Search } from 'lucide-react'

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
  isProbeCacheFresh,
} from '@/features/gateway-credentials/credential-probe-cache'
import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { ModelType } from '@/types/user-model'
import { MODEL_TYPE_LABELS } from '@/types/user-model'

export type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'

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
    default:
      return { label: support, variant: 'outline' }
  }
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

function UpstreamModelList({
  items,
  selected,
  onToggle,
  onPickModelId,
}: {
  items: CredentialProbeResult['items']
  selected: Set<string>
  onToggle: (id: string) => void
  onPickModelId?: (id: string) => void
}): React.JSX.Element {
  return (
    <div className="max-h-56 space-y-1 overflow-y-auto overscroll-y-contain rounded-md border p-2 text-sm [content-visibility:auto]">
      {items.map((it) => (
        <label
          key={it.id}
          className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-muted/60"
        >
          <Checkbox
            checked={selected.has(it.id)}
            onCheckedChange={() => {
              onToggle(it.id)
            }}
          />
          <span className="font-mono text-xs">{it.id}</span>
          {it.owned_by ? (
            <span className="text-xs text-muted-foreground">· {it.owned_by}</span>
          ) : null}
          {onPickModelId ? (
            <Button
              type="button"
              variant="link"
              className="ml-auto h-7 px-1 text-xs"
              onClick={(e) => {
                e.preventDefault()
                onPickModelId(it.id)
              }}
            >
              填入
            </Button>
          ) : null}
        </label>
      ))}
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

  const [probe, setProbe] = useState<CredentialProbeResult | null>(() =>
    readCachedProbe(queryClient, cacheKey)
  )
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')
  const [displayNamePrefix, setDisplayNamePrefix] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [capability, setCapability] = useState('chat')
  const [modelTypes, setModelTypes] = useState<ModelType[]>(['text'])

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
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '探测失败', description: e.message })
    },
  })

  // 单次 effect：凭据/缓存键变化时同步缓存；autoProbe 时仅在无缓存或缓存仍新鲜时跳过网络请求
  useEffect(() => {
    const cached = readCachedProbe(queryClient, cacheKey)
    if (cached) applyProbeResult(cached)

    if (!autoProbe || disabled || credentialId.length === 0) return
    if (probeMutation.isPending) return
    if (isProbeCacheFresh(queryClient, cacheKey)) return
    if (cached) return
    probeMutation.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在打开/凭据变化时自动探测
  }, [autoProbe, disabled, credentialId, cacheKey, queryClient, applyProbeResult])

  const batchMutation = useMutation({
    mutationFn: async () => {
      const ids = [...selected]
      if (ids.length === 0) throw new Error('请至少选择一条上游模型')
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
      toast({
        title: '导入完成',
        description: `成功 ${String(res.created.length)} 条，失败 ${String(res.failed.length)} 条`,
      })
      setSelected(new Set())
      if (res.created.length > 0) onImported?.(res.created.length)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '批量导入失败', description: e.message })
    },
  })

  const filteredItems = useMemo(() => {
    if (!probe?.items) return []
    const q = filter.trim().toLowerCase()
    if (!q) return probe.items
    return probe.items.filter((it) => it.id.toLowerCase().includes(q))
  }, [probe, filter])

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleAllVisible = useCallback(() => {
    const ids = filteredItems.map((i) => i.id)
    if (ids.length === 0) return
    const allSelected = ids.every((id) => selected.has(id))
    setSelected((prev) => {
      const next = new Set(prev)
      if (allSelected) ids.forEach((id) => next.delete(id))
      else ids.forEach((id) => next.add(id))
      return next
    })
  }, [filteredItems, selected])

  const runProbe = useCallback(() => {
    probeMutation.mutate()
  }, [probeMutation])

  const badge = probe ? supportBadge(probe.support) : null

  function toggleModelType(t: ModelType): void {
    setModelTypes((cur) => {
      const next = cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]
      return next.length === 0 ? ['text'] : next
    })
  }

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2">
      {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || probeMutation.isPending}
        onClick={runProbe}
      >
        {probeMutation.isPending ? (
          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
        ) : (
          <Search className="mr-1 h-3.5 w-3.5" />
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
      >
        <RefreshCw className="h-3.5 w-3.5" />
      </Button>
    </div>
  )

  const statusBlock =
    probe && (probe.support === 'unsupported' || probe.support === 'error') ? (
      <ProbeStatusAlert probe={probe} />
    ) : probe?.message && probe.support === 'full' ? (
      <p className="text-sm text-muted-foreground">{probe.message}</p>
    ) : null

  const listBlock =
    probe?.support === 'full' && probe.items.length > 0 ? (
      <>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid flex-1 gap-1.5">
            <Label htmlFor="upstream-filter">筛选 id</Label>
            <Input
              id="upstream-filter"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value)
              }}
              placeholder="gpt-4…"
            />
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="shrink-0"
            onClick={toggleAllVisible}
          >
            全选/取消可见项
          </Button>
        </div>
        <UpstreamModelList
          items={filteredItems}
          selected={selected}
          onToggle={toggle}
          onPickModelId={onPickModelId}
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
            <div className="grid gap-1.5">
              <Label htmlFor="team-cap">主调用面 capability</Label>
              <Input
                id="team-cap"
                value={capability}
                onChange={(e) => {
                  setCapability(e.target.value)
                }}
                placeholder="chat"
              />
            </div>
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
            <Label>模型类型（写入多行 personal gateway_models）</Label>
            <div className="flex flex-wrap gap-3">
              {(['text', 'image', 'image_gen', 'video'] as ModelType[]).map((t) => (
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
          </div>
        ) : null}
        <div className="flex justify-end">
          <Button
            type="button"
            disabled={disabled || batchMutation.isPending || selected.size === 0}
            onClick={() => {
              batchMutation.mutate()
            }}
          >
            {batchMutation.isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
            导入选中项（{selected.size}）
          </Button>
        </div>
      </>
    ) : probe?.support === 'full' && probe.items.length === 0 ? (
      <p className="text-sm text-muted-foreground" role="status">
        上游未返回任何模型。
      </p>
    ) : !probe && !probeMutation.isPending ? (
      <p className="text-sm text-muted-foreground">点击「探测」列举上游可用模型。</p>
    ) : null

  const pendingBlock =
    probeMutation.isPending && !probe ? (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        正在探测上游…
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
