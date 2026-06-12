/**
 * AI Gateway · 凭据详情（编辑、轮换密钥、启用/禁用、关联模型）
 *
 * 设计要点：
 * - 表单状态被抽到 {@link CredentialEditForm}，由父组件用 `key={cred.id::api_key_masked}`
 *   重挂代替 `useEffect` 派生 state，避免 react-query 后台 refetch 重置用户正在编辑的表单。
 * - 头部「启用」Switch 走独立的乐观更新 mutation，UI 即时响应。
 */

import { Suspense, useCallback, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  type GatewayCredentialUpdateBody,
  type ProviderCredential,
  type ProviderPlan,
  type ProviderPlanCost,
} from '@/api/gateway'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { CredentialBudgetSection } from '@/features/gateway-budget/credential-budget-section'
import { isConfigManagedSystemCredential } from '@/features/gateway-credentials/config-managed-credential'
import { CredentialDeleteConfirmDialog } from '@/features/gateway-credentials/credential-delete-confirm-dialog'
import { CredentialEditFields } from '@/features/gateway-credentials/credential-edit-fields'
import { CredentialModelsCard } from '@/features/gateway-credentials/credential-linked-models'
import {
  canEditGatewayCredential,
  canLinkToCredentialDetail,
  canManageSystemCredentialVisibility,
  isWritableTargetTeam,
} from '@/features/gateway-credentials/credential-permissions'
import { invalidateCredentialProbeCache } from '@/features/gateway-credentials/credential-probe-cache'
import {
  CredentialScopeBadge,
  CredentialTeamBadge,
  CredentialVisibilityBadge,
} from '@/features/gateway-credentials/credential-scope-display'
import { useProviderProfilesCatalog } from '@/features/gateway-credentials/hooks/use-provider-profiles-catalog'
import { getProviderSchema, providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { SystemCredentialVisibilityCard } from '@/features/gateway-credentials/system-credential-visibility-card'
import { managedCredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { invalidateCredentialSummariesCache } from '@/features/gateway-credentials/use-credential-directory'
import { useCredentialEditForm } from '@/features/gateway-credentials/use-credential-edit-form'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import {
  credentialsSystemBrowseIndexHref,
  credentialsTeamListHref,
} from '@/features/gateway-models/paths'
import { gatewayModelsByCredentialInvalidatePrefix } from '@/features/gateway-models/query-keys'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { switchGatewayTeam } from '@/features/gateway-teams/navigate-team'
import {
  resolveGatewayTeamLabel,
  useGatewayTeamNameMap,
  useGatewayWritableTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId, useGatewayTeamRecord } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { ChevronRight, Loader2, Trash2 } from '@/lib/lucide-icons'
import { useCurrentUser } from '@/stores/user'

const AddModelsDialog = lazyWithReload(() =>
  import('@/features/gateway-credentials/add-models-dialog').then((m) => ({
    default: m.AddModelsDialog,
  }))
)

export default function GatewayCredentialDetailPage(): React.JSX.Element {
  useProviderProfilesCatalog()
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const location = useLocation()
  const writableTeams = useGatewayWritableTeams()
  const teamNameById = useGatewayTeamNameMap()
  const currentTeam = useGatewayTeamRecord(teamId)
  const { credentialId } = useParams<{ credentialId: string }>()
  const id = credentialId ?? ''
  const [searchParams, setSearchParams] = useSearchParams()
  const [addModelsOpen, setAddModelsOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { canWrite, isPlatformAdmin, isAdmin } = useGatewayPermission()
  const currentUser = useCurrentUser()
  const viewerUserId = currentUser?.id ?? null

  const {
    data: cred,
    isLoading,
    isError,
    error,
    isFetching,
    refetch: refetchCredential,
  } = useQuery({
    queryKey: ['gateway', 'credential', teamId, id],
    queryFn: () => gatewayApi.getCredential(teamId, id),
    enabled: id.length > 0,
  })

  const editable = cred
    ? canEditGatewayCredential(cred, viewerUserId, canWrite, isPlatformAdmin)
    : false
  const linkable = cred
    ? canLinkToCredentialDetail(cred, viewerUserId, canWrite, isPlatformAdmin)
    : false
  const ownerTenantId =
    cred?.scope === 'team' && cred.tenant_id !== null && cred.tenant_id !== teamId && linkable
      ? cred.tenant_id
      : null
  const wrongTeamContext = ownerTenantId !== null
  const canSwitchToOwnerTeam =
    ownerTenantId !== null && isWritableTargetTeam(ownerTenantId, writableTeams)
  const canManageVisibility = canManageSystemCredentialVisibility(isPlatformAdmin)
  const configManaged = cred !== undefined && isConfigManagedSystemCredential(cred)
  const upstreamScope = cred ? managedCredentialUpstreamScope(cred.scope) : 'team'
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
      invalidateCredentialProbeCache(queryClient, upstreamScope, id)
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

  const handleDeleteDialogOpenChange = useCallback((open: boolean) => {
    setDeleteDialogOpen(open)
  }, [])

  const handleDeleteConfirm = useCallback(() => {
    deleteMutation.mutate()
  }, [deleteMutation])

  const handleRefresh = useCallback((): void => {
    void Promise.all([
      refetchCredential(),
      queryClient.invalidateQueries({ queryKey: ['gateway', 'credential', teamId, id] }),
      queryClient.invalidateQueries({
        queryKey: gatewayModelsByCredentialInvalidatePrefix(id, teamId),
      }),
    ])
    invalidateCredentialSummariesCache(queryClient)
  }, [id, queryClient, refetchCredential, teamId])

  if (!id) {
    return (
      <div className="text-sm text-muted-foreground">
        无效的凭据 ID。
        <Link
          to={credentialsTeamListHref(teamId)}
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
          to={credentialsTeamListHref(teamId)}
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
        <Link to={credentialsListHref} className="hover:text-foreground">
          凭据管理
        </Link>
        <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
        <span className="font-medium text-foreground">{cred.name}</span>
      </nav>

      {wrongTeamContext && ownerTenantId ? (
        <Alert>
          <AlertTitle>工作区与凭据归属不一致</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>
              此凭据属于「
              {teamNameById.get(ownerTenantId) ?? ownerTenantId.slice(0, 8)}」，当前工作区为「
              {currentTeam
                ? currentTeam.kind === 'personal'
                  ? '个人工作区'
                  : currentTeam.name
                : resolveGatewayTeamLabel(teamNameById, teamId)}
              」。
            </span>
            {canSwitchToOwnerTeam ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7"
                onClick={() => {
                  switchGatewayTeam(ownerTenantId, navigate, location, queryClient)
                }}
              >
                切换到所属团队
              </Button>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{cred.name}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{providerLabel(cred.provider)}</span>
            <span className="font-mono text-[11px]">({cred.provider})</span>
            <CredentialScopeBadge scope={cred.scope} />
            {cred.scope === 'team' && cred.tenant_id ? (
              <CredentialTeamBadge tenantId={cred.tenant_id} teamNameById={teamNameById} />
            ) : null}
            {cred.scope === 'system' ? (
              <CredentialVisibilityBadge visibility={cred.visibility} />
            ) : null}
            {cred.profile_label ? <Badge variant="outline">{cred.profile_label}</Badge> : null}
            {configManaged ? (
              <span className="text-xs text-amber-700 dark:text-amber-400">
                （配置同步托管，名称不可改）
              </span>
            ) : null}
          </div>
          {cred.effective_api_base_openai || cred.effective_api_base_anthropic ? (
            <div className="mt-2 space-y-1 text-xs text-muted-foreground">
              {cred.effective_api_base_openai ? (
                <p>
                  OpenAI-compat 根：
                  <span className="ml-1 font-mono text-[11px]">
                    {cred.effective_api_base_openai}
                  </span>
                </p>
              ) : null}
              {cred.effective_api_base_anthropic ? (
                <p>
                  Anthropic-native 根：
                  <span className="ml-1 font-mono text-[11px]">
                    {cred.effective_api_base_anthropic}
                  </span>
                </p>
              ) : null}
            </div>
          ) : null}
          {schema?.helpText ? (
            <p className="mt-1 text-xs text-muted-foreground">{schema.helpText}</p>
          ) : null}
        </div>
        {editable ? (
          <div className="flex flex-wrap items-center gap-2">
            <GatewayRefreshButton
              isFetching={isFetching}
              ariaLabel="刷新凭据详情"
              onRefresh={handleRefresh}
            />
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
          <div className="flex items-center gap-2">
            <GatewayRefreshButton
              isFetching={isFetching}
              ariaLabel="刷新凭据详情"
              onRefresh={handleRefresh}
            />
            <span className="text-sm text-muted-foreground">
              {cred.is_active ? '已启用' : '已禁用'}
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-6">
        {cred.scope === 'system' && canManageVisibility ? (
          <SystemCredentialVisibilityCard cred={cred} teamId={teamId} />
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle>凭据与密钥</CardTitle>
            <CardDescription>
              默认显示掩码；需要时可查看完整密钥，或点「更换」输入新密钥后保存。
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
                invalidateCredentialProbeCache(queryClient, upstreamScope, id)
                invalidateCredentialSummariesCache(queryClient)
              }}
            />
          </CardContent>
        </Card>

        <ProviderPlansSection teamId={teamId} credentialId={id} />

        {currentUser?.id ? (
          <CredentialBudgetSection
            credentialId={id}
            userId={currentUser.id}
            isAdmin={isAdmin}
            canSelfManage={
              !isAdmin &&
              cred.scope === 'team' &&
              (cred.created_by_user_id ?? null) === currentUser.id
            }
          />
        ) : null}

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
              scope={upstreamScope}
              credentialId={id}
              provider={cred.provider}
              credentialName={cred.name}
              isActive={cred.is_active}
            />
          </Suspense>
        ) : null}
      </div>

      <CredentialDeleteConfirmDialog
        credential={deleteDialogOpen ? cred : null}
        isPending={deleteMutation.isPending}
        onOpenChange={handleDeleteDialogOpenChange}
        onConfirm={handleDeleteConfirm}
      />
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
  const { items: linkedModels, isLoading: modelsLoading } = useInfiniteGatewayModelPages(
    teamId,
    {
      registry_scope: modelsTab === 'system' ? 'system' : 'callable',
      credential_id: credentialId,
    },
    { enabled: credentialId.length > 0, prefetchMode: 'idle' }
  )
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
  const form = useCredentialEditForm({ cred, configManaged })
  const credId = cred.id

  const revealFn = useCallback(() => gatewayApi.revealCredential(teamId, credId), [teamId, credId])

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
        queryKey: gatewayModelsByCredentialInvalidatePrefix(credId, teamId),
      })
      form.clearApiKey()
      toast({ title: '凭据已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  function handleSave(): void {
    if (!editable || !form.canSave) return
    updateMutation.mutate(form.buildUpdateBody())
  }

  return (
    <>
      <CredentialEditFields
        cred={cred}
        idPrefix="cred-detail"
        form={form}
        configManaged={configManaged}
        revealFn={revealFn}
        canReveal={editable}
        editable={editable}
      />
      {editable ? (
        <Button
          disabled={updateMutation.isPending || !form.canSave}
          onClick={() => {
            handleSave()
          }}
        >
          {updateMutation.isPending ? '保存中…' : '保存更改'}
        </Button>
      ) : null}
    </>
  )
}
