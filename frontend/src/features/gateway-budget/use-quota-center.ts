import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  type QuotaRule,
  type QuotaRuleBatchUpsertResponse,
  type QuotaRuleLayer,
  type QuotaRuleUpsertBody,
} from '@/api/gateway'
import { useGatewayVirtualKeys } from '@/features/gateway-keys/use-gateway-virtual-keys'
import { useGatewayRoutes } from '@/features/gateway-models/hooks/use-gateway-routes'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'
import { useGatewayTeamMembers } from '@/features/gateway-teams/use-gateway-team-members'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId, useGatewayTeamRecord } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { useCurrentUser } from '@/stores/user'
import { formatTeamMemberDisplay } from '@/types/permissions'

import { parseOptionalInt, parseOptionalUsd } from './budget-form-utils'
import { buildBudgetModelOptions, type BudgetModelOption } from './budget-model-options'
import { quotaRuleToBatchFormValues, type EditingRuleInfo } from './quota-batch-from-rule'
import { quotaRuleRowId, type QuotaRuleLabelContext } from './quota-rule-utils'
import { gatewayBudgetsBaseQueryKey } from './use-gateway-budgets'
import {
  GATEWAY_QUOTA_META_STALE_MS,
  gatewayQuotaRulesBaseQueryKey,
  useGatewayQuotaRules,
} from './use-gateway-quota-rules'

export interface QuotaBatchFormValues {
  layer: QuotaRuleLayer
  subjectMode: 'tenant' | 'users' | 'keys'
  userIds: string[]
  keyIds: string[]
  credentialIds: string[]
  modelNames: string[]
  allModels: boolean
  allCredentials: boolean
  period: 'daily' | 'monthly' | 'total'
  windowSeconds: string
  quotaLabel: string
  limit_usd: string
  limit_tokens: string
  limit_requests: string
}

export const DEFAULT_BATCH_FORM: QuotaBatchFormValues = {
  layer: 'platform',
  subjectMode: 'tenant',
  userIds: [],
  keyIds: [],
  credentialIds: [],
  modelNames: [],
  allModels: true,
  allCredentials: true,
  period: 'monthly',
  windowSeconds: '0',
  quotaLabel: 'default',
  limit_usd: '',
  limit_tokens: '',
  limit_requests: '',
}

/** 切换层级时清理与当前层级无关的字段，避免预览条数异常 */
export function patchQuotaBatchFormForLayer(
  values: QuotaBatchFormValues,
  layer: QuotaRuleLayer
): QuotaBatchFormValues {
  if (layer === 'platform') {
    const subjectMode = values.subjectMode
    return {
      ...values,
      layer,
      subjectMode,
      // 仅「指定成员」可附带凭据维度；其余主体清空凭据选择。
      credentialIds: subjectMode === 'users' ? values.credentialIds : [],
      userIds: subjectMode === 'users' ? values.userIds : [],
      keyIds: subjectMode === 'keys' ? values.keyIds : [],
    }
  }
  if (layer === 'upstream') {
    return {
      ...values,
      layer,
      subjectMode: 'tenant',
      userIds: [],
      keyIds: [],
    }
  }
  return {
    ...values,
    layer,
    subjectMode: 'keys',
    userIds: [],
    credentialIds: [],
  }
}

export function patchQuotaBatchFormForSubjectMode(
  values: QuotaBatchFormValues,
  subjectMode: QuotaBatchFormValues['subjectMode']
): QuotaBatchFormValues {
  return {
    ...values,
    subjectMode,
    userIds: subjectMode === 'users' ? values.userIds : [],
    keyIds: subjectMode === 'keys' ? values.keyIds : [],
    credentialIds: subjectMode === 'users' ? values.credentialIds : [],
  }
}

function expandBatchFormValues(
  values: QuotaBatchFormValues,
  credentialIds: readonly string[]
): QuotaBatchFormValues {
  if (values.layer === 'upstream' && values.allCredentials) {
    return {
      ...values,
      allCredentials: false,
      credentialIds: [...credentialIds],
    }
  }
  return values
}

function buildBatchRules(values: QuotaBatchFormValues): QuotaRuleUpsertBody[] | null {
  const lu = parseOptionalUsd(values.limit_usd)
  const lt = parseOptionalInt(values.limit_tokens)
  const lr = parseOptionalInt(values.limit_requests)
  if (lu === null && lt === null && lr === null) return null

  const models = values.allModels ? [null] : values.modelNames.map((m) => m || null)
  if (!values.allModels && models.length === 0) return null

  const rules: QuotaRuleUpsertBody[] = []

  if (values.layer === 'platform') {
    const subjects: { target_kind: QuotaRuleUpsertBody['target_kind']; target_id?: string }[] = []
    if (values.subjectMode === 'tenant') {
      subjects.push({ target_kind: 'tenant' })
    } else if (values.subjectMode === 'users') {
      for (const uid of values.userIds) {
        subjects.push({ target_kind: 'user', target_id: uid })
      }
    } else {
      for (const kid of values.keyIds) {
        subjects.push({ target_kind: 'key', target_id: kid })
      }
    }
    if (subjects.length === 0) return null
    // 仅 target_kind=user 允许附带凭据（成员+凭据+模型）；选了凭据时做成员×凭据×模型笛卡尔积。
    for (const sub of subjects) {
      const credTargets =
        sub.target_kind === 'user' && values.credentialIds.length > 0
          ? values.credentialIds
          : [null]
      for (const credId of credTargets) {
        for (const model of models) {
          const body: QuotaRuleUpsertBody = {
            layer: 'platform',
            target_kind: sub.target_kind,
            period: values.period,
          }
          if (sub.target_id) body.target_id = sub.target_id
          if (credId) body.credential_id = credId
          if (model) body.model_name = model
          if (lu !== null) body.limit_usd = lu
          if (lt !== null) body.limit_tokens = lt
          if (lr !== null) body.limit_requests = lr
          rules.push(body)
        }
      }
    }
    return rules
  }

  if (values.layer === 'upstream') {
    const creds = values.allCredentials ? [] : values.credentialIds
    if (!values.allCredentials && creds.length === 0) return null
    const credentialTargets = values.allCredentials ? [null] : creds
    const ws = parseOptionalInt(values.windowSeconds) ?? 0
    for (const credId of credentialTargets) {
      for (const model of models) {
        const body: QuotaRuleUpsertBody = {
          layer: 'upstream',
          window_seconds: ws,
          quota_label: values.quotaLabel.trim() || 'default',
        }
        if (credId) body.credential_id = credId
        if (model) body.model_name = model
        if (lu !== null) body.limit_usd = lu
        if (lt !== null) body.limit_tokens = lt
        if (lr !== null) body.limit_requests = lr
        rules.push(body)
      }
    }
    return rules
  }

  const ws = parseOptionalInt(values.windowSeconds) ?? 0
  if (values.keyIds.length === 0) return null
  for (const kid of values.keyIds) {
    for (const model of models) {
      const body: QuotaRuleUpsertBody = {
        layer: 'downstream',
        access_kind: 'vkey',
        access_id: kid,
        window_seconds: ws,
        quota_label: values.quotaLabel.trim() || 'default',
      }
      if (model) body.model_name = model
      if (lu !== null) body.limit_usd = lu
      if (lt !== null) body.limit_tokens = lt
      if (lr !== null) body.limit_requests = lr
      rules.push(body)
    }
  }
  return rules
}

export type QuotaCenterMode = 'admin' | 'member'

export interface QuotaCenterState {
  teamId: string
  teamName: string
  mode: QuotaCenterMode
  formDisabled: boolean
  isLoading: boolean
  isRefreshing: boolean
  filteredItems: QuotaRule[]
  selectedRule: QuotaRule | null
  selectedId: string | null
  selectRule: (rule: QuotaRule) => void
  clearSelection: () => void
  labelContext: QuotaRuleLabelContext
  layerFilter: string
  modelFilter: string
  periodFilter: string
  setFilter: (key: 'layer' | 'model' | 'period', value: string) => void
  batchOpen: boolean
  setBatchOpen: (open: boolean) => void
  batchValues: QuotaBatchFormValues
  setBatchValues: (values: QuotaBatchFormValues) => void
  submitBatch: () => void
  batchPending: boolean
  confirmDelete: (rule: QuotaRule) => void
  confirmBatchDelete: (rules: QuotaRule[]) => Promise<void>
  deletePending: boolean
  refresh: () => void
  memberOptions: { id: string; label: string }[]
  keyOptions: { id: string; label: string }[]
  credentialOptions: {
    id: string
    label: string
    provider: string
    scope: string | null
    isLegacy?: boolean
  }[]
  metaLoading: boolean
  modelOptions: BudgetModelOption[]
  modelsLoading: boolean
  onModelPickerOpenChange?: (open: boolean) => void
  batchPreviewCount: number
  /** 当前处于编辑状态的规则信息；null 表示创建/批量模式 */
  editingRuleId: string | null
  onEditRule: (rule: QuotaRule) => void
  /** 编辑模式下删除当前规则并关闭向导 */
  deleteEditingRule: () => void
}

function useQuotaCenterImpl(): QuotaCenterState {
  const teamId = useGatewayTeamId()
  const teamRecord = useGatewayTeamRecord(teamId)
  const { toast } = useToast()
  const { isAdmin, isPlatformViewer } = useGatewayPermission()
  const currentUser = useCurrentUser()
  const selfUserId = currentUser?.id ?? null
  const mode: QuotaCenterMode = isAdmin ? 'admin' : 'member'
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  const layerFilter = searchParams.get('layer') ?? 'all'
  const modelFilter = searchParams.get('model') ?? ''
  const periodFilter = searchParams.get('period') ?? 'all'
  // 成员自助：从凭据详情「设置我的限额 →」带入的凭据预填，用于预加载凭据元数据并自动开抽屉。
  const credentialPrefill = mode === 'member' ? searchParams.get('credential_id') : null
  // 管理员：统计页「设配额」/ 凭据详情跳转带入的成员、凭据预填。
  const userPrefill = mode === 'admin' ? searchParams.get('user_id') : null
  const adminCredentialPrefill = mode === 'admin' ? searchParams.get('credential_id') : null

  const [batchOpen, setBatchOpen] = useState(false)
  const [batchValues, setBatchValues] = useState<QuotaBatchFormValues>(DEFAULT_BATCH_FORM)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null)
  const editingInfoRef = useRef<EditingRuleInfo | null>(null)

  const listParams = useMemo(
    () => ({
      layer: layerFilter === 'all' ? undefined : (layerFilter as QuotaRuleLayer),
      model_name: modelFilter || undefined,
      period: periodFilter === 'all' ? undefined : (periodFilter as 'daily' | 'monthly' | 'total'),
      include_usage: true,
    }),
    [layerFilter, modelFilter, periodFilter]
  )

  const rulesQuery = useGatewayQuotaRules(teamId, listParams)

  const needsPickerData = batchOpen || modelFilter.trim() !== ''
  const needsLabelData =
    batchOpen || (rulesQuery.data?.length ?? 0) > 0 || credentialPrefill !== null || isAdmin

  const keysQuery = useGatewayVirtualKeys(teamId, {
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

  const membersQuery = useGatewayTeamMembers(teamId)

  const credsQuery = useQuery({
    queryKey: ['gateway', 'credential-summaries', teamId],
    queryFn: () => gatewayApi.listCredentialSummaries(teamId),
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

  const modelPages = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { enabled: needsPickerData, prefetchMode: 'open' }
  )

  const routesQuery = useGatewayRoutes(teamId, {
    enabled: teamId.length > 0 && needsPickerData,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const existingModelNames = useMemo(
    () => (rulesQuery.data ?? []).map((r) => r.key.model_name),
    [rulesQuery.data]
  )

  const modelOptions = useMemo(
    () =>
      buildBudgetModelOptions({
        models: modelPages.items,
        routes: routesQuery.data ?? [],
        existingModelNames,
      }),
    [modelPages.items, routesQuery.data, existingModelNames]
  )

  const labelContext: QuotaRuleLabelContext = useMemo(() => {
    const memberLabels = new Map<string, string>()
    for (const m of membersQuery.data ?? []) {
      memberLabels.set(m.user_id, formatTeamMemberDisplay(m).primary)
    }
    const keyLabels = new Map<string, string>()
    for (const k of keysQuery.data ?? []) {
      keyLabels.set(k.id, k.name)
    }
    const credentialLabels = new Map<string, string>()
    for (const c of credsQuery.data ?? []) {
      credentialLabels.set(c.id, c.name)
    }
    return { memberLabels, keyLabels, credentialLabels }
  }, [membersQuery.data, keysQuery.data, credsQuery.data])

  // 周期等筛选由后端 list 参数完成（滚动窗口型 upstream/downstream 规则的保留规则在服务端），
  // 此处不再二次过滤，避免与服务端语义不一致导致规则"消失"。
  const filteredItems = useMemo(() => rulesQuery.data ?? [], [rulesQuery.data])

  const selectedRule = useMemo(
    () => filteredItems.find((r) => quotaRuleRowId(r) === selectedId) ?? null,
    [filteredItems, selectedId]
  )

  const batchMutation = useMutation({
    mutationFn: (rules: QuotaRuleUpsertBody[]) =>
      mode === 'member'
        ? gatewayApi.batchUpsertSelfQuotaRules(teamId, rules)
        : gatewayApi.batchUpsertQuotaRules(teamId, rules),
    onSuccess: (result: QuotaRuleBatchUpsertResponse) => {
      void queryClient.invalidateQueries({ queryKey: gatewayQuotaRulesBaseQueryKey(teamId) })
      void queryClient.invalidateQueries({ queryKey: gatewayBudgetsBaseQueryKey(teamId) })
      if (result.failed.length > 0) {
        toast({
          title: `部分成功：${String(result.succeeded.length)} 条`,
          description: result.failed.map((f) => f.error).join('；'),
          variant: 'destructive',
        })
      } else {
        toast({ title: `已保存 ${String(result.succeeded.length)} 条配额规则` })
      }
      handleSetBatchOpen(false)
    },
    onError: (err: Error) => {
      toast({ title: '保存失败', description: err.message, variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (budgetId: string) =>
      mode === 'member'
        ? gatewayApi.deleteSelfQuotaRule(teamId, budgetId)
        : gatewayApi.deleteBudget(teamId, budgetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: gatewayQuotaRulesBaseQueryKey(teamId) })
      void queryClient.invalidateQueries({ queryKey: gatewayBudgetsBaseQueryKey(teamId) })
      setSelectedId(null)
      toast({ title: '已删除配额规则' })
    },
    onError: (err: Error) => {
      toast({ title: '删除失败', description: err.message, variant: 'destructive' })
    },
  })

  const setFilter = useCallback(
    (key: 'layer' | 'model' | 'period', value: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (value === '' || value === 'all') next.delete(key)
        else next.set(key, value)
        return next
      })
    },
    [setSearchParams]
  )

  const credentialOptions = useMemo(() => {
    const raw = credsQuery.data ?? []
    if (mode === 'member') {
      // 成员自助：展示「本人创建的团队凭据」+「无明确创建者的团队凭据」（legacy 凭据）+「个人 BYOK 凭据」
      const result: {
        id: string
        label: string
        provider: string
        scope: string | null
        isLegacy?: boolean
      }[] = []
      for (const c of raw) {
        // 个人凭据（scope='user'）直接显示
        if (c.scope === 'user') {
          result.push({
            id: c.id,
            label: c.name,
            provider: c.provider,
            scope: c.scope,
          })
        }
        // 团队凭据：本人创建的或无明确创建者的（legacy）
        else if (
          selfUserId !== null &&
          (c.created_by_user_id === selfUserId || c.created_by_user_id === null)
        ) {
          result.push({
            id: c.id,
            label: c.name,
            provider: c.provider,
            scope: c.scope,
            isLegacy: c.created_by_user_id === null,
          })
        }
      }
      return result
    }
    return raw.map((c) => ({
      id: c.id,
      label: c.name,
      provider: c.provider,
      scope: c.scope,
      isLegacy: c.created_by_user_id === null,
    }))
  }, [credsQuery.data, mode, selfUserId])

  const credentialIds = useMemo(() => credentialOptions.map((c) => c.id), [credentialOptions])

  const resolvedBatchValues = useMemo(
    () => expandBatchFormValues(batchValues, credentialIds),
    [batchValues, credentialIds]
  )

  const batchPreviewCount = useMemo(() => {
    let v = resolvedBatchValues
    if (mode === 'member') {
      v = {
        ...resolvedBatchValues,
        layer: 'platform',
        subjectMode: 'users',
        userIds: selfUserId !== null ? [selfUserId] : [],
        keyIds: [],
      }
    }
    return buildBatchRules(v)?.length ?? 0
  }, [resolvedBatchValues, mode, selfUserId])

  const memberOptions = useMemo(
    () =>
      (membersQuery.data ?? []).map((m) => ({
        id: m.user_id,
        label: formatTeamMemberDisplay(m).primary,
      })),
    [membersQuery.data]
  )

  const keyOptions = useMemo(
    () => (keysQuery.data ?? []).map((k) => ({ id: k.id, label: k.name })),
    [keysQuery.data]
  )

  const submitBatch = useCallback(() => {
    let formValues = resolvedBatchValues
    // 编辑模式：保留原始维度，仅改限额与模型
    if (editingRuleId && editingInfoRef.current) {
      formValues = resolvedBatchValues
      // 不强制覆盖为成员自助锁定
    } else if (mode === 'member') {
      // 成员自助：强制锁定为本人 + platform，凭据必选。
      if (selfUserId === null) {
        toast({ title: '无法识别当前用户', variant: 'destructive' })
        return
      }
      if (resolvedBatchValues.credentialIds.length === 0) {
        toast({
          title: '请选择凭据',
          description:
            '自助配额须选择至少一个凭据。如列表为空，请先在凭据页添加团队凭据，或联系管理员。',
          variant: 'destructive',
        })
        return
      }
      formValues = {
        ...resolvedBatchValues,
        layer: 'platform',
        subjectMode: 'users',
        userIds: [selfUserId],
        keyIds: [],
      }
    } else if (editingRuleId) {
      // 编辑模式兜底：若校验通过且非 member/admin 兜底路径，
      // 直接按表单值提交（维度已锁定，仅限额变更）。
      formValues = resolvedBatchValues
    }
    const rules = buildBatchRules(formValues)
    if (!rules || rules.length === 0) {
      toast({
        title: '请完善表单',
        description: '至少选择主体并填写一项限额',
        variant: 'destructive',
      })
      return
    }
    if (rules.length > 200) {
      toast({ title: '单次最多 200 条', variant: 'destructive' })
      return
    }
    batchMutation.mutate(rules)
  }, [resolvedBatchValues, batchMutation, toast, mode, selfUserId, editingRuleId])

  const confirmDelete = useCallback(
    (rule: QuotaRule) => {
      const budgetId = rule.source_ref.budget_id
      if (!budgetId) {
        toast({ title: '计划类配额请至凭据/Key 页管理', variant: 'destructive' })
        return
      }
      // P11: 删除确认 — 直接执行删除，由调用方展示确认对话框
      deleteMutation.mutate(budgetId)
    },
    [deleteMutation, toast]
  )

  /** 编辑模式下删除当前规则 */
  const deleteEditingRule = useCallback(() => {
    if (!editingRuleId) return
    const budgetId = editingRuleId
    deleteMutation.mutate(budgetId, {
      onSuccess: () => {
        setBatchOpen(false)
      },
    })
  }, [editingRuleId, deleteMutation])

  const confirmBatchDelete = useCallback(
    async (rules: QuotaRule[]) => {
      const deletable = rules.filter((r) => r.source_ref.budget_id !== null)
      if (deletable.length === 0) {
        toast({
          title: '所选规则均不可删除（计划类配额请至凭据/Key 页管理）',
          variant: 'destructive',
        })
        return
      }
      const results = await Promise.allSettled(
        deletable.map((r) => {
          const budgetId = r.source_ref.budget_id
          // deletable 已过滤 budget_id !== null，此处安全断言
          return deleteMutation.mutateAsync(budgetId as string)
        })
      )
      const succeeded = results.filter((r) => r.status === 'fulfilled').length
      const failed = results.filter((r) => r.status === 'rejected').length
      if (failed > 0) {
        toast({
          title: `批量删除完成：${String(succeeded)} 条成功，${String(failed)} 条失败`,
          variant: failed === deletable.length ? 'destructive' : 'default',
        })
      } else {
        toast({ title: `已删除 ${String(succeeded)} 条配额规则` })
      }
    },
    [deleteMutation, toast]
  )

  // 成员自助：从凭据详情「设置我的限额 →」跳转时，待 owned 凭据加载后预填并自动开抽屉。
  const consumedPrefillRef = useRef<string | null>(null)
  useEffect(() => {
    if (credentialPrefill === null) return
    if (consumedPrefillRef.current === credentialPrefill) return
    if (!credentialOptions.some((c) => c.id === credentialPrefill)) return
    consumedPrefillRef.current = credentialPrefill
    setBatchValues({
      ...DEFAULT_BATCH_FORM,
      subjectMode: 'users',
      credentialIds: [credentialPrefill],
      allModels: modelFilter.trim() === '',
      modelNames: modelFilter.trim() === '' ? [] : [modelFilter.trim()],
    })
    setBatchOpen(true)
  }, [credentialPrefill, modelFilter, credentialOptions])

  // 管理员：统计页「设配额」（user_id）/ 凭据详情（credential_id + layer=upstream）跳转预填并自动开抽屉。
  const consumedAdminPrefillRef = useRef<string | null>(null)
  useEffect(() => {
    if (mode !== 'admin') return
    if (userPrefill === null && adminCredentialPrefill === null) return
    const token = `${userPrefill ?? ''}|${adminCredentialPrefill ?? ''}`
    if (consumedAdminPrefillRef.current === token) return
    consumedAdminPrefillRef.current = token
    const model = modelFilter.trim()
    const modelFields = {
      allModels: model === '',
      modelNames: model === '' ? [] : [model],
    }
    if (userPrefill !== null) {
      setBatchValues({
        ...DEFAULT_BATCH_FORM,
        subjectMode: 'users',
        userIds: [userPrefill],
        credentialIds: adminCredentialPrefill ? [adminCredentialPrefill] : [],
        ...modelFields,
      })
    } else if (adminCredentialPrefill !== null) {
      // 仅凭据无成员：platform 层凭据维度必须挂在成员上，故落到 upstream 层。
      setBatchValues({
        ...DEFAULT_BATCH_FORM,
        layer: 'upstream',
        allCredentials: false,
        credentialIds: [adminCredentialPrefill],
        ...modelFields,
      })
    }
    setBatchOpen(true)
  }, [mode, userPrefill, adminCredentialPrefill, modelFilter])

  const selectRule = useCallback((rule: QuotaRule) => {
    setSelectedId(quotaRuleRowId(rule))
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedId(null)
  }, [])

  const onEditRule = useCallback(
    (rule: QuotaRule) => {
      const parsed = quotaRuleToBatchFormValues(rule)
      if (!parsed) {
        toast({
          title: '暂不支持编辑此规则',
          description: '上游/下游配额及计划类规则请在凭据/Key 页管理。',
          variant: 'destructive',
        })
        return
      }
      editingInfoRef.current = parsed.info
      setEditingRuleId(parsed.info.budgetId)
      setBatchValues(parsed.values)
      setBatchOpen(true)
    },
    [toast]
  )

  const handleSetBatchOpen = useCallback((open: boolean) => {
    setBatchOpen(open)
    if (!open) {
      setEditingRuleId(null)
      editingInfoRef.current = null
    }
  }, [])

  const refresh = useCallback(() => {
    void rulesQuery.refetch()
  }, [rulesQuery])

  return {
    teamId,
    teamName: teamRecord?.name ?? teamId.slice(0, 8),
    mode,
    // 平台只读账号全站不可写；成员模式下若无法识别本人则禁用自助写入。
    formDisabled: isPlatformViewer || (mode === 'member' && selfUserId === null),
    isLoading: rulesQuery.isLoading,
    isRefreshing: rulesQuery.isFetching,
    filteredItems,
    selectedRule,
    selectedId,
    selectRule,
    clearSelection,
    labelContext,
    layerFilter,
    modelFilter,
    periodFilter,
    setFilter,
    batchOpen,
    setBatchOpen: handleSetBatchOpen,
    batchValues,
    setBatchValues,
    submitBatch,
    batchPending: batchMutation.isPending,
    confirmDelete,
    confirmBatchDelete,
    deletePending: deleteMutation.isPending,
    refresh,
    memberOptions,
    keyOptions,
    credentialOptions,
    metaLoading:
      batchOpen && (membersQuery.isLoading || keysQuery.isLoading || credsQuery.isLoading),
    modelOptions,
    modelsLoading: modelPages.isLoading || routesQuery.isLoading,
    onModelPickerOpenChange: modelPages.onPickerOpenChange,
    batchPreviewCount,
    editingRuleId,
    onEditRule,
    deleteEditingRule,
  }
}

export function useQuotaCenter(): QuotaCenterState {
  return useQuotaCenterImpl()
}
