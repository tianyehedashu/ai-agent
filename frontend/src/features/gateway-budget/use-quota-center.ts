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
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { useCurrentUser } from '@/stores/user'
import { formatTeamMemberDisplay } from '@/types/permissions'

import { parseOptionalInt, parseOptionalUsd } from './budget-form-utils'
import { buildBudgetModelOptions, type BudgetModelOption } from './budget-model-options'
import { quotaRuleRowId, type QuotaRuleLabelContext } from './quota-rule-utils'
import {
  GATEWAY_QUOTA_META_STALE_MS,
  gatewayQuotaRulesQueryKey,
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
  credentialOptions: { id: string; label: string }[]
  metaLoading: boolean
  modelOptions: BudgetModelOption[]
  modelsLoading: boolean
  onModelPickerOpenChange?: (open: boolean) => void
  batchPreviewCount: number
}

function useQuotaCenterImpl(): QuotaCenterState {
  const teamId = useGatewayTeamId()
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

  const [batchOpen, setBatchOpen] = useState(false)
  const [batchValues, setBatchValues] = useState<QuotaBatchFormValues>(DEFAULT_BATCH_FORM)
  const [selectedId, setSelectedId] = useState<string | null>(null)

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
    batchOpen || (rulesQuery.data?.length ?? 0) > 0 || credentialPrefill !== null

  const keysQuery = useQuery({
    queryKey: ['gateway', 'keys', teamId],
    queryFn: () => gatewayApi.listKeys(teamId),
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

  const membersQuery = useQuery({
    queryKey: ['gateway', 'members', teamId],
    queryFn: () => gatewayApi.listMembers(teamId),
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

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

  const routesQuery = useQuery({
    queryKey: ['gateway', 'routes', teamId],
    queryFn: () => gatewayApi.listRoutes(teamId),
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

  const filteredItems = useMemo(() => {
    let items = rulesQuery.data ?? []
    if (periodFilter !== 'all') {
      items = items.filter(
        (r) => r.key.period === periodFilter || (r.key.period === null && periodFilter === 'total')
      )
    }
    return items
  }, [rulesQuery.data, periodFilter])

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
      void queryClient.invalidateQueries({ queryKey: ['gateway-quota-rules', teamId] })
      void queryClient.invalidateQueries({ queryKey: ['gateway-budgets', teamId] })
      if (result.failed.length > 0) {
        toast({
          title: `部分成功：${String(result.succeeded.length)} 条`,
          description: result.failed.map((f) => f.error).join('；'),
          variant: 'destructive',
        })
      } else {
        toast({ title: `已保存 ${String(result.succeeded.length)} 条配额规则` })
      }
      setBatchOpen(false)
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
      void queryClient.invalidateQueries({ queryKey: gatewayQuotaRulesQueryKey(teamId) })
      void queryClient.invalidateQueries({ queryKey: ['gateway-budgets', teamId] })
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
    let creds = credsQuery.data ?? []
    if (mode === 'member') {
      // 成员自助仅能设置「本人创建的团队凭据」（个人 BYOK 凭据在凭据页就地设限）。
      creds = creds.filter((c) => selfUserId !== null && c.created_by_user_id === selfUserId)
    }
    return creds.map((c) => ({ id: c.id, label: c.name }))
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
    if (mode === 'member') {
      // 成员自助：强制锁定为本人 + platform，凭据必选。
      if (selfUserId === null) {
        toast({ title: '无法识别当前用户', variant: 'destructive' })
        return
      }
      if (resolvedBatchValues.credentialIds.length === 0) {
        toast({
          title: '请选择本人凭据',
          description: '自助配额须指定本人创建的凭据',
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
  }, [resolvedBatchValues, batchMutation, toast, mode, selfUserId])

  const confirmDelete = useCallback(
    (rule: QuotaRule) => {
      const budgetId = rule.source_ref.budget_id
      if (!budgetId) {
        toast({ title: '计划类配额请至凭据/Key 页管理', variant: 'destructive' })
        return
      }
      deleteMutation.mutate(budgetId)
    },
    [deleteMutation, toast]
  )

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
      let succeeded = 0
      let failed = 0
      for (const rule of deletable) {
        const budgetId = rule.source_ref.budget_id
        if (!budgetId) continue
        try {
          await deleteMutation.mutateAsync(budgetId)
          succeeded++
        } catch {
          failed++
        }
      }
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

  const selectRule = useCallback((rule: QuotaRule) => {
    setSelectedId(quotaRuleRowId(rule))
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedId(null)
  }, [])

  const refresh = useCallback(() => {
    void rulesQuery.refetch()
  }, [rulesQuery])

  return {
    teamId,
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
    setBatchOpen,
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
  }
}

export function useQuotaCenter(): QuotaCenterState {
  return useQuotaCenterImpl()
}
