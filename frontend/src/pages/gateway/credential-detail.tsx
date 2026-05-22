/**
 * AI Gateway · 凭据详情（编辑、轮换密钥、启用/禁用、关联模型）
 *
 * 设计要点：
 * - 表单状态被抽到 {@link CredentialEditForm}，由父组件用 `key={cred.id::api_key_masked}`
 *   重挂代替 `useEffect` 派生 state，避免 react-query 后台 refetch 重置用户正在编辑的表单。
 * - 头部「启用」Switch 走独立的乐观更新 mutation，UI 即时响应。
 */

import { lazy, Suspense, useCallback, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  type GatewayCredentialUpdateBody,
  type ProviderCredential,
  type ProviderPlan,
  type ProviderPlanCost,
} from '@/api/gateway'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { isConfigManagedSystemCredential } from '@/features/gateway-credentials/config-managed-credential'
import { canEditGatewayCredential } from '@/features/gateway-credentials/credential-edit-policy'
import { ExtraFieldsRenderer } from '@/features/gateway-credentials/credential-extra-fields'
import {
  compactExtra,
  extraToFormValues,
  type CredentialExtraValues,
} from '@/features/gateway-credentials/credential-extra-utils'
import { CredentialModelsCard } from '@/features/gateway-credentials/credential-linked-models'
import { invalidateCredentialProbeCache } from '@/features/gateway-credentials/credential-probe-cache'
import {
  apiKeyLabelForProvider,
  defaultApiBaseForProvider,
  extraFieldsForProvider,
  getProviderSchema,
  providerLabel,
} from '@/features/gateway-credentials/provider-schemas'
import { SystemCredentialVisibilityCard } from '@/features/gateway-credentials/system-credential-visibility-card'
import { invalidateCredentialSummariesCache } from '@/features/gateway-credentials/use-credential-directory'
import {
  credentialsSystemBrowseIndexHref,
  credentialsTeamListHref,
} from '@/features/gateway-models/paths'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { ChevronRight, Loader2, Trash2 } from '@/lib/lucide-icons'

const AddModelsDialog = lazy(() =>
  import('@/features/gateway-credentials/add-models-dialog').then((m) => ({
    default: m.AddModelsDialog,
  }))
)

export default function GatewayCredentialDetailPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const { credentialId } = useParams<{ credentialId: string }>()
  const id = credentialId ?? ''
  const [searchParams, setSearchParams] = useSearchParams()
  const [addModelsOpen, setAddModelsOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { canWrite, isPlatformAdmin } = useGatewayPermission()

  const {
    data: cred,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['gateway', 'credential', teamId, id],
    queryFn: () => gatewayApi.getCredential(teamId, id),
    enabled: id.length > 0,
  })

  const editable = cred ? canEditGatewayCredential(cred, canWrite, isPlatformAdmin) : false
  const configManaged = cred !== undefined && isConfigManagedSystemCredential(cred)
  const credentialsListHref =
    cred?.scope === 'system'
      ? credentialsSystemBrowseIndexHref(teamId)
      : credentialsTeamListHref(teamId)
  const schema = cred ? getProviderSchema(cred.provider) : undefined

  const addModelsFromUrl = searchParams.get('addModels') === '1'
  const showAddModelsDialog = Boolean(cred) && editable && (addModelsOpen || addModelsFromUrl)

  const handleAddModelsOpenChange = useCallback(
    (open: boolean) => {
      setAddModelsOpen(open)
      if (!open && addModelsFromUrl) {
        setSearchParams(
          (prev) => {
            const n = new URLSearchParams(prev)
            n.delete('addModels')
            return n
          },
          { replace: true }
        )
      }
    },
    [addModelsFromUrl, setSearchParams]
  )

  const openAddModelsDialog = useCallback(() => {
    setAddModelsOpen(true)
  }, [])

  // 头部「启用/禁用」走独立 mutation + 乐观更新，UI 即时响应，不再依赖本地 isActive state
  const toggleActiveMutation = useMutation({
    mutationFn: (nextActive: boolean) =>
      gatewayApi.updateCredential(teamId, id, { is_active: nextActive }),
    onMutate: async (nextActive: boolean) => {
      await queryClient.cancelQueries({ queryKey: ['gateway', 'credential', teamId, id] })
      const previous = queryClient.getQueryData<ProviderCredential>([
        'gateway',
        'credential',
        teamId,
        id,
      ])
      if (previous) {
        queryClient.setQueryData<ProviderCredential>(['gateway', 'credential', teamId, id], {
          ...previous,
          is_active: nextActive,
        })
      }
      return { previous }
    },
    onError: (e: Error, _next, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(['gateway', 'credential', teamId, id], ctx.previous)
      }
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
    onSettled: () => {
      invalidateCredentialProbeCache(queryClient, 'team', id)
      invalidateCredentialSummariesCache(queryClient)
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credential', teamId, id] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => gatewayApi.deleteCredential(teamId, id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      invalidateCredentialSummariesCache(queryClient)
      setDeleteDialogOpen(false)
      toast({ title: '凭据已删除', description: '关联的注册模型已一并移除' })
      navigate(credentialsListHref)
    },
    onError: (e: Error) => {
      setDeleteDialogOpen(false)
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  if (!id) {
    return (
      <div className="text-sm text-muted-foreground">
        无效的凭据 ID。
        <Link
          to={`/gateway/teams/${teamId}/credentials?tab=shared`}
          className="ml-2 text-primary underline-offset-4 hover:underline"
        >
          返回列表
        </Link>
      </div>
    )
  }

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">加载中…</div>
  }

  if (isError || !cred) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-destructive">
          {error instanceof Error ? error.message : '无法加载凭据'}
        </p>
        <Link
          to={`/gateway/teams/${teamId}/credentials?tab=shared`}
          className="text-primary underline-offset-4 hover:underline"
        >
          返回凭据列表
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
        <Link
          to={`/gateway/teams/${teamId}/credentials?tab=shared`}
          className="hover:text-foreground"
        >
          凭据管理
        </Link>
        <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
        <span className="font-medium text-foreground">{cred.name}</span>
      </nav>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{cred.name}</h2>
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{providerLabel(cred.provider)}</span>
            <span className="ml-1.5 font-mono text-[11px]">({cred.provider})</span>
            <span className="mx-2">·</span>
            <span>{cred.scope}</span>
            {cred.scope === 'system' ? <span className="ml-2 text-xs">（系统全局）</span> : null}
            {configManaged ? (
              <span className="ml-2 text-xs text-amber-700 dark:text-amber-400">
                （配置同步托管，名称不可改）
              </span>
            ) : null}
          </p>
          {schema?.helpText ? (
            <p className="mt-1 text-xs text-muted-foreground">{schema.helpText}</p>
          ) : null}
        </div>
        {editable ? (
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 rounded-md border px-3 py-2">
              <Label htmlFor="cred-header-active" className="cursor-pointer text-sm font-normal">
                {cred.is_active ? '已启用' : '已禁用'}
              </Label>
              <Switch
                id="cred-header-active"
                checked={cred.is_active}
                disabled={toggleActiveMutation.isPending}
                onCheckedChange={(checked) => {
                  toggleActiveMutation.mutate(checked)
                }}
                aria-label={cred.is_active ? '停用凭据' : '启用凭据'}
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              disabled={deleteMutation.isPending || toggleActiveMutation.isPending}
              onClick={() => {
                setDeleteDialogOpen(true)
              }}
            >
              {deleteMutation.isPending ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-1 h-4 w-4" />
              )}
              删除凭据
            </Button>
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">
            {cred.is_active ? '已启用' : '已禁用'}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-6">
        {cred.scope === 'system' && isPlatformAdmin ? (
          <SystemCredentialVisibilityCard cred={cred} teamId={teamId} />
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle>凭据与密钥</CardTitle>
            <CardDescription>
              默认显示掩码。打开「显示完整密钥」可查看当前值；轮换请在下方填写新密钥后保存。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <CredentialEditForm
              teamId={teamId}
              // 用 cred.id + api_key_masked 复合 key：
              //  · 切换凭据时重挂（清空所有 form state）
              //  · 同一凭据轮换 key 成功后也重挂（清空「显示完整密钥」状态）
              //  · 同一凭据的 is_active 改变不会触发重挂（避免编辑中表单被吞）
              key={`${cred.id}::${cred.api_key_masked}`}
              cred={cred}
              editable={editable}
              configManaged={configManaged}
              onSaved={() => {
                invalidateCredentialProbeCache(queryClient, 'team', id)
                invalidateCredentialSummariesCache(queryClient)
              }}
            />
          </CardContent>
        </Card>

        <ProviderPlansSection teamId={teamId} credentialId={id} />

        <CredentialLinkedModelsSection
          teamId={teamId}
          credentialId={id}
          canManageModels={editable}
          modelsTab={cred.scope === 'system' ? 'system' : 'shared'}
          onAddModels={editable ? openAddModelsDialog : undefined}
        />

        {showAddModelsDialog ? (
          <Suspense
            fallback={
              <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                加载添加模型…
              </div>
            }
          >
            <AddModelsDialog
              open
              onOpenChange={handleAddModelsOpenChange}
              scope="team"
              credentialId={id}
              provider={cred.provider}
              credentialName={cred.name}
              isActive={cred.is_active}
            />
          </Suspense>
        ) : null}
      </div>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除凭据</AlertDialogTitle>
            <AlertDialogDescription>
              {configManaged
                ? `确定删除「${cred.name}」？将同时删除所有引用该凭据的注册模型；此为配置同步凭据，下次从配置重载或重启后可能自动恢复。`
                : `确定删除「${cred.name}」？将同时删除所有引用该凭据的注册模型，并更新虚拟 Key / 路由中的模型白名单。`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
              onClick={() => {
                deleteMutation.mutate()
              }}
            >
              {deleteMutation.isPending ? '删除中…' : '删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function formatDateTime(value: string): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

function formatMoney(value: number | string | null | undefined): string {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? `$${n.toFixed(4)}` : '$0.0000'
}

function formatQuotaLimit(plan: ProviderPlan): string {
  if (plan.quotas.length === 0) return '不限'
  return plan.quotas
    .map((q) => {
      const limits = [
        q.limit_requests !== null ? `${String(q.limit_requests)} req` : null,
        q.limit_tokens !== null ? `${String(q.limit_tokens)} token` : null,
        q.limit_usd !== null ? formatMoney(q.limit_usd) : null,
      ].filter(Boolean)
      const strategy =
        q.reset_strategy === 'calendar_daily_utc'
          ? '每日 UTC'
          : q.reset_strategy === 'calendar_monthly_utc'
            ? '自然月'
            : q.reset_strategy === 'plan_anniversary'
              ? '订阅锚点'
              : '滚动'
      return `${q.label}：${limits.join(' / ') || '不限'} · ${strategy}`
    })
    .join('；')
}

function usageByPlanId(rows: ProviderPlanCost[] | undefined): Map<string, ProviderPlanCost> {
  return new Map((rows ?? []).map((row) => [row.plan_id, row]))
}

function ProviderPlansSection({
  teamId,
  credentialId,
}: Readonly<{
  teamId: string
  credentialId: string
}>): React.JSX.Element {
  const { data: plans, isLoading: plansLoading } = useQuery({
    queryKey: ['gateway', 'credential', teamId, credentialId, 'provider-plans'],
    queryFn: () => gatewayApi.listProviderPlans(teamId, credentialId),
    enabled: credentialId.length > 0,
  })
  const { data: usage } = useQuery({
    queryKey: ['gateway', 'credential', teamId, credentialId, 'provider-plan-usage', 30],
    queryFn: () => gatewayApi.listProviderPlanUsage(teamId, credentialId, { days: 30 }),
    enabled: credentialId.length > 0,
  })
  const usageMap = useMemo(() => usageByPlanId(usage), [usage])

  return (
    <Card>
      <CardHeader>
        <CardTitle>厂商套餐</CardTitle>
        <CardDescription>
          上游购买的套餐额度。若厂商返回配额耗尽，系统会立即同步本地套餐状态并触发路由 fallback。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {plansLoading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : (plans?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">暂无厂商套餐；该凭据按普通按量模式路由。</p>
        ) : (
          <div className="space-y-2">
            {plans?.map((plan) => {
              const row = usageMap.get(plan.id)
              const activeNow =
                plan.is_active &&
                new Date(plan.valid_from).getTime() <= Date.now() &&
                new Date(plan.valid_until).getTime() > Date.now()
              return (
                <div key={plan.id} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{plan.label}</p>
                        <Badge variant={activeNow ? 'default' : 'secondary'}>
                          {activeNow ? '生效中' : plan.is_active ? '未在有效期' : '已停用'}
                        </Badge>
                        {plan.auto_renew ? <Badge variant="outline">自动续期</Badge> : null}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {plan.real_model ?? '整凭据共享'} · {formatDateTime(plan.valid_from)} →{' '}
                        {formatDateTime(plan.valid_until)}
                      </p>
                    </div>
                    <div className="text-right text-xs tabular-nums text-muted-foreground">
                      <p>30 天请求：{String(row?.requests ?? 0)}</p>
                      <p>成本：{formatMoney(row?.cost_usd)}</p>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{formatQuotaLimit(plan)}</p>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * 拉取并展示该凭据关联的注册模型。独立成段，避免与编辑表单耦合 query 失效逻辑。
 */
function CredentialLinkedModelsSection({
  teamId,
  credentialId,
  canManageModels,
  modelsTab = 'shared',
  onAddModels,
}: Readonly<{
  teamId: string
  credentialId: string
  canManageModels: boolean
  modelsTab?: 'shared' | 'system'
  onAddModels?: () => void
}>): React.JSX.Element {
  const { data: linkedModels, isLoading: modelsLoading } = useQuery({
    queryKey: ['gateway', 'models', teamId, 'by-credential', credentialId, modelsTab],
    queryFn: () =>
      gatewayApi.listModels(teamId, {
        registry_scope: modelsTab === 'system' ? 'system' : 'callable',
        credential_id: credentialId,
      }),
    enabled: credentialId.length > 0,
  })
  return (
    <CredentialModelsCard
      credentialId={credentialId}
      models={linkedModels}
      isLoading={modelsLoading}
      canManageModels={canManageModels}
      modelsTab={modelsTab}
      onAddModels={onAddModels}
    />
  )
}

/**
 * 凭据编辑表单：表单 state 由 `cred` lazy init，**不再用 useEffect 派生**。
 * 父组件需通过 `key` 触发重挂以在切换凭据或轮换 key 后重置状态。
 */
function CredentialEditForm({
  teamId,
  cred,
  editable,
  configManaged,
  onSaved,
}: Readonly<{
  teamId: string
  cred: ProviderCredential
  editable: boolean
  configManaged: boolean
  onSaved?: () => void
}>): React.JSX.Element {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [name, setName] = useState<string>(() => cred.name)
  const [apiBase, setApiBase] = useState<string>(() => cred.api_base ?? '')
  const [apiKey, setApiKey] = useState<string>('')
  const [extra, setExtra] = useState<CredentialExtraValues>(() => extraToFormValues(cred.extra))
  const [showFullCurrentKey, setShowFullCurrentKey] = useState(false)
  const [revealedCurrentKey, setRevealedCurrentKey] = useState<string | null>(null)

  const credId = cred.id

  const revealKeyMutation = useMutation({
    mutationFn: () => gatewayApi.revealCredential(teamId, credId),
    onSuccess: (data) => {
      setRevealedCurrentKey(data.api_key)
    },
    onError: (e: Error) => {
      toast({
        variant: 'destructive',
        title: '无法显示完整密钥',
        description: e.message,
      })
      setShowFullCurrentKey(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: (body: GatewayCredentialUpdateBody) =>
      gatewayApi.updateCredential(teamId, credId, body),
    onSuccess: () => {
      onSaved?.()
      invalidateCredentialSummariesCache(queryClient)
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credential', teamId, credId] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({
        queryKey: ['gateway', 'models', 'by-credential', credId],
      })
      setApiKey('')
      toast({ title: '凭据已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const provider = cred.provider
  const schema = getProviderSchema(provider)
  const extraFields = useMemo(() => extraFieldsForProvider(provider), [provider])
  const apiKeyLabel = apiKeyLabelForProvider(provider)
  const defaultApiBase = defaultApiBaseForProvider(provider)
  const baseIsDefault = defaultApiBase.length > 0 && apiBase === defaultApiBase
  const apiBasePlaceholder =
    schema?.apiBasePlaceholder ??
    (defaultApiBase.length > 0 ? defaultApiBase : 'https://example.com/v1')
  const apiBaseRequired = schema?.apiBaseRequired ?? false
  const apiBaseMissing = apiBaseRequired && !apiBase.trim()
  const requiredExtraMissing = extraFields.some((f) => f.required && !(extra[f.key] ?? '').trim())

  const compactedNow = useMemo(() => compactExtra(extra), [extra])
  const compactedOrig = useMemo(() => compactExtra(extraToFormValues(cred.extra)), [cred.extra])
  const synced =
    name === cred.name &&
    (apiBase.trim() || '') === (cred.api_base ?? '') &&
    apiKey === '' &&
    JSON.stringify(compactedNow) === JSON.stringify(compactedOrig)

  const canSave = Boolean(name.trim()) && !apiBaseMissing && !requiredExtraMissing && !synced

  const credExtra = cred.extra
  const hasUnknownExtra =
    extraFields.length === 0 && credExtra !== null && Object.keys(credExtra).length > 0

  function handleSave(): void {
    if (!editable || !name.trim()) return
    const body: GatewayCredentialUpdateBody = {
      api_base: apiBase.trim() || null,
      extra: Object.keys(compactedNow).length > 0 ? compactedNow : null,
    }
    if (!configManaged) body.name = name.trim()
    if (apiKey.trim()) body.api_key = apiKey.trim()
    updateMutation.mutate(body)
  }

  return (
    <>
      <div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <Label htmlFor="cred-current-key">当前 {apiKeyLabel}</Label>
          {editable ? (
            <div className="flex items-center gap-2 sm:pb-0.5">
              <Label
                htmlFor="cred-show-full-key"
                className="cursor-pointer text-xs font-normal text-muted-foreground"
              >
                显示完整密钥
              </Label>
              <Switch
                id="cred-show-full-key"
                checked={showFullCurrentKey}
                disabled={revealKeyMutation.isPending}
                onCheckedChange={(checked) => {
                  setShowFullCurrentKey(checked)
                  if (!checked) {
                    setRevealedCurrentKey(null)
                    revealKeyMutation.reset()
                    return
                  }
                  revealKeyMutation.mutate()
                }}
              />
            </div>
          ) : null}
        </div>
        <Input
          id="cred-current-key"
          readOnly
          className="mt-1.5 font-mono text-xs"
          value={
            showFullCurrentKey
              ? revealKeyMutation.isPending && revealedCurrentKey === null
                ? '加载中…'
                : (revealedCurrentKey ?? '')
              : cred.api_key_masked
          }
        />
      </div>
      {editable ? (
        <>
          <div>
            <Label htmlFor="cred-detail-name">名称</Label>
            <Input
              id="cred-detail-name"
              className="mt-1.5"
              value={name}
              readOnly={configManaged}
              disabled={configManaged}
              onChange={(e) => {
                setName(e.target.value)
              }}
            />
            {configManaged ? (
              <p className="mt-1 text-xs text-muted-foreground">
                该凭据由 app.toml / 环境变量同步维护，重命名会导致重复凭据。
              </p>
            ) : null}
          </div>
          <div>
            <Label htmlFor="cred-detail-new-key">新 {apiKeyLabel}（留空则不变）</Label>
            <Input
              id="cred-detail-new-key"
              type="password"
              autoComplete="new-password"
              className="mt-1.5"
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
              }}
              placeholder={schema?.apiKeyPlaceholder}
            />
            {schema?.apiKeyHelpText ? (
              <p className="mt-1 text-xs text-muted-foreground">{schema.apiKeyHelpText}</p>
            ) : null}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Label htmlFor="cred-detail-base">
                api_base
                {apiBaseRequired ? (
                  <span className="ml-1 text-destructive">*</span>
                ) : (
                  <span className="ml-1 text-[11px] text-muted-foreground">（可选）</span>
                )}
              </Label>
              {baseIsDefault ? (
                <Badge variant="outline" className="px-1 py-0 text-[10px]">
                  默认
                </Badge>
              ) : null}
            </div>
            <Input
              id="cred-detail-base"
              className="mt-1.5"
              value={apiBase}
              onChange={(e) => {
                setApiBase(e.target.value)
              }}
              placeholder={apiBasePlaceholder}
            />
            {defaultApiBase.length > 0 && !baseIsDefault ? (
              <p className="mt-1 text-xs text-muted-foreground">
                该 provider 的默认地址：
                <button
                  type="button"
                  className="ml-1 font-mono text-primary underline-offset-2 hover:underline"
                  onClick={() => {
                    setApiBase(defaultApiBase)
                  }}
                >
                  {defaultApiBase}
                </button>
              </p>
            ) : null}
          </div>
          {extraFields.length > 0 ? (
            <ExtraFieldsRenderer
              fields={extraFields}
              values={extra}
              onChange={setExtra}
              idPrefix="cred-detail-extra"
            />
          ) : hasUnknownExtra ? (
            <div>
              <Label>extra（未知字段，只读）</Label>
              <pre className="mt-1.5 max-h-40 overflow-auto rounded-md border bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
                {JSON.stringify(credExtra, null, 2)}
              </pre>
              <p className="mt-1 text-xs text-muted-foreground">
                当前 provider 未声明 extra schema；如需编辑请在 schema 中追加字段。
              </p>
            </div>
          ) : null}
          <Button
            disabled={updateMutation.isPending || !canSave}
            onClick={() => {
              handleSave()
            }}
          >
            {updateMutation.isPending ? '保存中…' : '保存更改'}
          </Button>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">你无权编辑此凭据（系统凭据需平台管理员）。</p>
      )}
    </>
  )
}
